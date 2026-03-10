import React, { useEffect, useMemo, useState } from 'react';
import {
  ActivityIndicator,
  Alert,
  Image,
  Modal,
  Platform,
  Pressable,
  ScrollView,
  SafeAreaView,
  StatusBar,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';

// import {

// } from 'react-native-safe-area-context';
import { Feather } from '@expo/vector-icons';
import * as ImagePicker from 'expo-image-picker';

import { ExpenseCategory } from './types';
import { apiService } from './services/api.native';
import { inferReceiptWithBackend } from './services/receiptInference.native';

type TabKey = 'home' | 'groups' | 'spending' | 'balance';
type AppUser = { id: number; name: string; email?: string };
type AppGroup = { id: number; name: string; code: string };
type BalanceTransfer = { from: string; to: string; amount: number; groupName: string };
type EditableExpenseItem = { id: string; description: string; amountInput: string; participants: number[] };
type AppExpensePreview = { id: number; title: string; totalAmount: number; date: string };
type ReceiptProcessingSource = 'donut' | 'manual';
type GroupDetailData = {
  groupId: number;
  name: string;
  code: string;
  members: AppUser[];
  balances: BalanceTransfer[];
  expenses: AppExpensePreview[];
};

const money = (v: number) => `${Number(v || 0).toFixed(2)} EUR`;

function parseMoneyInput(value: string): number {
  const normalized = value.replace(/\s+/g, '').replace(',', '.');
  const parsed = Number(normalized);
  return Number.isFinite(parsed) ? parsed : 0;
}

function toMoneyInput(value: number): string {
  return Number(value || 0).toFixed(2);
}

function formatExpenseDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value || '-';
  return date.toLocaleDateString('es-ES');
}

function TabButton({
  icon,
  label,
  active,
  onPress,
}: {
  icon: keyof typeof Feather.glyphMap;
  label: string;
  active: boolean;
  onPress: () => void;
}) {
  return (
    <Pressable style={styles.tabButton} onPress={onPress}>
      <Feather name={icon} size={22} color={active ? '#10b981' : '#9ca3af'} />
      <Text style={[styles.tabText, active ? styles.tabTextActive : null]}>{label}</Text>
    </Pressable>
  );
}

function Drawer({
  open,
  active,
  onClose,
  onSelect,
  topInset,
}: {
  open: boolean;
  active: TabKey;
  onClose: () => void;
  onSelect: (tab: TabKey) => void;
  topInset: number;
}) {
  const items: Array<{ key: TabKey; label: string }> = [
    { key: 'home', label: 'Inicio' },
    { key: 'groups', label: 'Grupos' },
    { key: 'balance', label: 'Balance' },
  ];

  return (
    <Modal visible={open} transparent animationType="fade" onRequestClose={onClose}>
      <Pressable style={styles.drawerOverlay} onPress={onClose}>
        <View style={[styles.drawerPanel, { paddingTop: 24 + topInset }]}>
          <Text style={styles.drawerTitle}>Menu</Text>
          {items.map((item) => (
            <Pressable
              key={item.key}
              style={[styles.drawerItem, active === item.key ? styles.drawerItemActive : null]}
              onPress={() => {
                onSelect(item.key);
                onClose();
              }}
            >
              <Text style={[styles.drawerItemText, active === item.key ? styles.drawerItemTextActive : null]}>{item.label}</Text>
            </Pressable>
          ))}
        </View>
      </Pressable>
    </Modal>
  );
}

function CreateGroupModal({
  open,
  users,
  me,
  onClose,
  onCreate,
}: {
  open: boolean;
  users: AppUser[];
  me: number;
  onClose: () => void;
  onCreate: (name: string, members: number[]) => Promise<void>;
}) {
  const [name, setName] = useState('');
  const [members, setMembers] = useState<number[]>([]);
  const [loading, setLoading] = useState(false);

  const toggle = (id: number) => {
    if (id === me) return;
    setMembers((prev) => (prev.includes(id) ? prev.filter((v) => v !== id) : [...prev, id]));
  };

  const submit = async () => {
    if (!name.trim()) {
      Alert.alert('Falta nombre', 'Introduce nombre de grupo.');
      return;
    }
    setLoading(true);
    try {
      await onCreate(name.trim(), Array.from(new Set([me, ...members])));
      setName('');
      setMembers([]);
      onClose();
    } finally {
      setLoading(false);
    }
  };

  return (
    <Modal visible={open} transparent animationType="slide" onRequestClose={onClose}>
      <View style={styles.modalOverlay}>
        <View style={styles.modalCard}>
          <Text style={styles.modalTitle}>Crear grupo</Text>
          <TextInput value={name} onChangeText={setName} style={styles.input} placeholder="Nombre del grupo" />
          <Text style={styles.modalLabel}>Anadir usuarios</Text>
          <ScrollView style={{ maxHeight: 220 }}>
            {users.map((u) => {
              const selected = u.id === me || members.includes(u.id);
              return (
                <Pressable key={u.id} onPress={() => toggle(u.id)} style={[styles.userRow, selected ? styles.userRowActive : null]}>
                  <Text style={styles.userName}>{u.name}</Text>
                  <Text style={styles.userMail}>{u.email || `#${u.id}`}</Text>
                </Pressable>
              );
            })}
          </ScrollView>
          <View style={styles.row}>
            <Pressable style={styles.softBtn} onPress={onClose}>
              <Text style={styles.softBtnText}>Cancelar</Text>
            </Pressable>
            <Pressable style={styles.mainBtn} onPress={submit} disabled={loading}>
              {loading ? <ActivityIndicator color="#fff" /> : <Text style={styles.mainBtnText}>Crear</Text>}
            </Pressable>
          </View>
        </View>
      </View>
    </Modal>
  );
}

function AddExpenseModal({
  open,
  groups,
  me,
  meName,
  initialGroupId,
  onClose,
  onCreated,
}: {
  open: boolean;
  groups: AppGroup[];
  me: number;
  meName: string;
  initialGroupId?: number | null;
  onClose: () => void;
  onCreated: () => Promise<void>;
}) {
  const [step, setStep] = useState<'upload' | 'processing' | 'review'>('upload');
  const [title, setTitle] = useState('Ticket');
  const [groupId, setGroupId] = useState<number | null>(null);
  const [uri, setUri] = useState('');
  const [totalInput, setTotalInput] = useState('0.00');
  const [items, setItems] = useState<EditableExpenseItem[]>([]);
  const [groupMembers, setGroupMembers] = useState<AppUser[]>([{ id: me, name: meName }]);
  const [expenseParticipants, setExpenseParticipants] = useState<number[]>([me]);
  const [membersLoading, setMembersLoading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [processingSource, setProcessingSource] = useState<ReceiptProcessingSource | null>(null);

  const expenseParticipantsSet = useMemo(() => new Set(expenseParticipants), [expenseParticipants]);
  const itemsTotal = useMemo(
    () => items.reduce((acc, item) => acc + parseMoneyInput(item.amountInput), 0),
    [items],
  );
  const availableMembers = useMemo(() => {
    if (groupId === null) return [{ id: me, name: meName }];
    return groupMembers.length > 0 ? groupMembers : [{ id: me, name: meName }];
  }, [groupId, groupMembers, me, meName]);
  const processingSourceMeta = useMemo(() => {
    if (processingSource === 'donut') {
      return {
        label: 'Donut backend',
        style: styles.processingBadgeDonut,
        textStyle: styles.processingBadgeTextDonut,
      };
    }
    if (processingSource === 'manual') {
      return {
        label: 'Modo manual',
        style: styles.processingBadgeManual,
        textStyle: styles.processingBadgeTextManual,
      };
    }
    return null;
  }, [processingSource]);

  useEffect(() => {
    let active = true;

    const loadGroupMembers = async () => {
      if (groupId === null) {
        const mine = [{ id: me, name: meName }];
        setGroupMembers(mine);
        setExpenseParticipants([me]);
        setItems((prev) => prev.map((item) => ({ ...item, participants: [me] })));
        setMembersLoading(false);
        return;
      }

      setMembersLoading(true);
      try {
        const groupData = await apiService.groups.get(String(groupId));
        if (!active) return;

        const members = Array.isArray(groupData?.members)
          ? groupData.members
              .map((member: any) => ({
                id: Number(member?.id),
                name: String(member?.name || `Usuario ${member?.id}`),
                email: typeof member?.email === 'string' ? member.email : '',
              }))
              .filter((member: AppUser) => Number.isFinite(member.id) && member.id > 0)
          : [];

        const normalizedMembers = members.length > 0 ? members : [{ id: me, name: meName }];
        const allowed = new Set(normalizedMembers.map((member) => member.id));
        setGroupMembers(normalizedMembers);
        setExpenseParticipants(normalizedMembers.map((member) => member.id));

        setItems((prev) =>
          prev.map((item) => {
            const validParticipants = item.participants.filter((id) => allowed.has(id));
            return {
              ...item,
              participants:
                validParticipants.length > 0
                  ? validParticipants
                  : normalizedMembers.map((member) => member.id),
            };
          }),
        );
      } catch {
        if (!active) return;
        setGroupMembers([{ id: me, name: meName }]);
        setExpenseParticipants([me]);
      } finally {
        if (active) setMembersLoading(false);
      }
    };

    void loadGroupMembers();
    return () => {
      active = false;
    };
  }, [groupId, me, meName]);

  const reset = () => {
    setStep('upload');
    setTitle('Ticket');
    setGroupId(initialGroupId ?? null);
    setUri('');
    setTotalInput('0.00');
    setItems([]);
    setGroupMembers([{ id: me, name: meName }]);
    setExpenseParticipants([me]);
    setMembersLoading(false);
    setProgress(0);
    setLoading(false);
    setError('');
    setProcessingSource(null);
  };

  const close = () => {
    reset();
    onClose();
  };

  useEffect(() => {
    if (!open) return;
    setStep('upload');
    setGroupId(initialGroupId ?? null);
    setError('');
    setProcessingSource(null);
  }, [open, initialGroupId]);

  const pick = async (camera: boolean) => {
    const permission = camera
      ? await ImagePicker.requestCameraPermissionsAsync()
      : await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (!permission.granted) {
      Alert.alert('Permiso requerido', camera ? 'Permite acceso a camara.' : 'Permite acceso a galeria.');
      return;
    }
    const result = camera
      ? await ImagePicker.launchCameraAsync({ mediaTypes: ['images'], quality: 0.9 })
      : await ImagePicker.launchImageLibraryAsync({ mediaTypes: ['images'], quality: 0.9 });
    if (!result.canceled && result.assets[0]?.uri) setUri(result.assets[0].uri);
  };

  const makeItemId = () => `${Date.now()}-${Math.random().toString(16).slice(2, 8)}`;
  const baseParticipants = () => (expenseParticipants.length > 0 ? expenseParticipants : [me]);

  const toggleExpenseParticipant = (userId: number) => {
    setExpenseParticipants((prev) => {
      const has = prev.includes(userId);
      if (has && prev.length === 1) return prev;

      const next = has ? prev.filter((id) => id !== userId) : [...prev, userId];
      const normalized = next.length > 0 ? next : [me];

      setItems((prevItems) =>
        prevItems.map((item) => {
          const valid = item.participants.filter((id) => normalized.includes(id));
          return {
            ...item,
            participants: valid.length > 0 ? valid : [normalized[0]],
          };
        }),
      );

      return normalized;
    });
  };

  const toggleItemParticipant = (itemId: string, userId: number) => {
    if (!expenseParticipantsSet.has(userId)) return;

    setItems((prev) =>
      prev.map((item) => {
        if (item.id !== itemId) return item;
        const has = item.participants.includes(userId);
        if (has && item.participants.length === 1) return item;
        return {
          ...item,
          participants: has
            ? item.participants.filter((id) => id !== userId)
            : [...item.participants, userId],
        };
      }),
    );
  };

  const updateItemField = (itemId: string, patch: Partial<EditableExpenseItem>) => {
    setItems((prev) => prev.map((item) => (item.id === itemId ? { ...item, ...patch } : item)));
  };

  const addManualItem = () => {
    setItems((prev) => [
      ...prev,
      {
        id: makeItemId(),
        description: '',
        amountInput: '0.00',
        participants: baseParticipants(),
      },
    ]);
  };

  const applyExtractedReceipt = (
    data: { total: number | null; items: Array<{ description: string; amount: number }> },
    source: ReceiptProcessingSource,
    warningMessage = '',
  ) => {
    const extractedItems: EditableExpenseItem[] = data.items.map((item) => ({
      id: makeItemId(),
      description: item.description,
      amountInput: toMoneyInput(Number(item.amount || 0)),
      participants: baseParticipants(),
    }));
    const extractedTotal = Number(data.total || 0);
    const fallbackItemsTotal = extractedItems.reduce((acc, item) => acc + parseMoneyInput(item.amountInput), 0);

    setTotalInput(toMoneyInput(extractedTotal > 0 ? extractedTotal : fallbackItemsTotal));
    setItems(
      extractedItems.length > 0
        ? extractedItems
        : [
            {
              id: makeItemId(),
              description: '',
              amountInput: '0.00',
              participants: baseParticipants(),
            },
          ],
    );
    setError(warningMessage);
    setProcessingSource(source);
    setStep('review');
  };

  const applyManualFallback = (message: string) => {
    const fallbackTotal = parseMoneyInput(totalInput);
    setTotalInput(toMoneyInput(fallbackTotal));
    if (fallbackTotal > 0) {
      setItems([
        {
          id: makeItemId(),
          description: title || 'Gasto',
          amountInput: toMoneyInput(fallbackTotal),
          participants: baseParticipants(),
        },
      ]);
    } else {
      setItems([]);
    }
    setError(message);
    setProcessingSource('manual');
    setStep('review');
  };

  const removeItem = (itemId: string) => {
    setItems((prev) => prev.filter((item) => item.id !== itemId));
  };

  const processReceipt = async () => {
    if (!uri) {
      setError('Selecciona una imagen.');
      return;
    }
    setLoading(true);
    setError('');
    setProgress(8);
    setStep('processing');
    try {
      const backendData = await inferReceiptWithBackend({ uri, mimeType: 'image/jpeg' });
      setProgress(100);
      console.log('[ReceiptInference] backend', {
        total: backendData.total,
        itemCount: backendData.items.length,
        engine: backendData.engine,
        confidence: backendData.confidence,
        debug: backendData.debug,
      });
      applyExtractedReceipt(backendData, 'donut');
    } catch (backendError: any) {
      const backendMessage = backendError?.message || 'Inferencia Donut no disponible';
      console.warn('[ReceiptInference] backend_failed', backendMessage);

      applyManualFallback(`${backendMessage}. Puedes guardar el gasto en modo manual.`);
    } finally {
      setLoading(false);
    }
  };

  const save = async () => {
    const selectedParticipants = groupId === null ? [me] : expenseParticipants;
    if (selectedParticipants.length === 0) {
      setError('Selecciona al menos un participante.');
      return;
    }

    const normalizedItems = items
      .map((item) => ({
        description: item.description.trim(),
        amount: parseMoneyInput(item.amountInput),
        participants: item.participants.filter((id) => selectedParticipants.includes(id)),
      }))
      .filter((item) => item.description.length > 0 && item.amount > 0)
      .map((item) => ({
        ...item,
        participants: item.participants.length > 0 ? item.participants : selectedParticipants,
      }));

    const manualTotal = parseMoneyInput(totalInput);
    const computedItemsTotal = normalizedItems.reduce((acc, item) => acc + item.amount, 0);
    const finalTotal = manualTotal > 0 ? manualTotal : computedItemsTotal;
    if (finalTotal <= 0) {
      setError('El total del gasto debe ser mayor que 0.');
      return;
    }

    const itemsForSave = normalizedItems.length > 0
      ? normalizedItems
      : [
          {
            description: title.trim() || 'Gasto',
            amount: finalTotal,
            participants: selectedParticipants,
          },
        ];

    setLoading(true);
    try {
      await apiService.expenses.create({
        title,
        totalAmount: finalTotal,
        category: ExpenseCategory.OTHERS,
        paidBy: me,
        groupId: groupId ?? undefined,
        participants: selectedParticipants,
        items: itemsForSave.map((it) => ({
          description: it.description,
          amount: Number(it.amount.toFixed(2)),
          category: ExpenseCategory.OTHERS,
          participants: it.participants,
        })),
      });
      await onCreated();
      close();
    } catch (e: any) {
      setError(e?.message || 'No se pudo guardar');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Modal visible={open} transparent animationType="slide" onRequestClose={close}>
      <View style={styles.modalOverlay}>
        <View style={styles.modalCard}>
          <Text style={styles.modalTitle}>Anadir gasto</Text>
          {step === 'upload' ? (
            <>
              <TextInput value={title} onChangeText={setTitle} style={styles.input} placeholder="Titulo" />
              <TextInput
                value={totalInput}
                onChangeText={setTotalInput}
                style={styles.input}
                keyboardType="decimal-pad"
                placeholder="Total manual (si falla el analisis)"
              />
              <ScrollView horizontal showsHorizontalScrollIndicator={false}>
                <View style={styles.tags}>
                  <Pressable style={[styles.tag, groupId === null ? styles.tagOn : null]} onPress={() => setGroupId(null)}>
                    <Text style={[styles.tagTx, groupId === null ? styles.tagTxOn : null]}>Personal</Text>
                  </Pressable>
                  {groups.map((g) => (
                    <Pressable key={g.id} style={[styles.tag, groupId === g.id ? styles.tagOn : null]} onPress={() => setGroupId(g.id)}>
                      <Text style={[styles.tagTx, groupId === g.id ? styles.tagTxOn : null]}>{g.name}</Text>
                    </Pressable>
                  ))}
                </View>
              </ScrollView>
              <View style={styles.preview}>{uri ? <Image source={{ uri }} style={styles.previewImg} /> : <Text style={styles.subtle}>Sin imagen</Text>}</View>
              <View style={styles.row}>
                <Pressable style={styles.softBtn} onPress={() => pick(false)}><Text style={styles.softBtnText}>Galeria</Text></Pressable>
                <Pressable style={styles.softBtn} onPress={() => pick(true)}><Text style={styles.softBtnText}>Camara</Text></Pressable>
              </View>
              <Pressable style={styles.mainBtn} onPress={processReceipt}><Text style={styles.mainBtnText}>Procesar ticket</Text></Pressable>
            </>
          ) : null}
          {step === 'processing' ? (
            <View style={styles.processing}>
              <ActivityIndicator size="large" color="#10b981" />
              <Text style={styles.subtle}>Procesando... {progress}%</Text>
            </View>
          ) : null}
          {step === 'review' ? (
            <>
              {processingSourceMeta ? (
                <View style={[styles.processingBadge, processingSourceMeta.style]}>
                  <Text style={[styles.processingBadgeText, processingSourceMeta.textStyle]}>
                    Procesado con {processingSourceMeta.label}
                  </Text>
                </View>
              ) : null}
              <Text style={styles.modalLabel}>Total del gasto</Text>
              <TextInput
                value={totalInput}
                onChangeText={setTotalInput}
                style={styles.input}
                keyboardType="decimal-pad"
                placeholder="0.00"
              />
              <View style={styles.panelRow}>
                <Text style={styles.subtle}>Suma items: {money(itemsTotal)}</Text>
                <Pressable style={styles.softMiniBtn} onPress={() => setTotalInput(toMoneyInput(itemsTotal))}>
                  <Text style={styles.softMiniBtnText}>Usar suma</Text>
                </Pressable>
              </View>

              <Text style={styles.modalLabel}>Participantes del gasto</Text>
              {membersLoading ? <ActivityIndicator color="#10b981" /> : null}
              <ScrollView horizontal showsHorizontalScrollIndicator={false}>
                <View style={styles.tags}>
                  {availableMembers.map((member) => {
                    const selected = expenseParticipants.includes(member.id);
                    return (
                      <Pressable
                        key={member.id}
                        style={[styles.tag, selected ? styles.tagOn : null]}
                        onPress={() => toggleExpenseParticipant(member.id)}
                      >
                        <Text style={[styles.tagTx, selected ? styles.tagTxOn : null]}>{member.name}</Text>
                      </Pressable>
                    );
                  })}
                </View>
              </ScrollView>

              <View style={styles.panelRow}>
                <Text style={styles.modalLabel}>Desglose del ticket</Text>
                <Pressable style={styles.softMiniBtn} onPress={addManualItem}>
                  <Text style={styles.softMiniBtnText}>Anadir linea</Text>
                </Pressable>
              </View>

              <ScrollView style={{ maxHeight: 250 }}>
                {items.map((item) => (
                  <View key={item.id} style={styles.itemCard}>
                    <TextInput
                      value={item.description}
                      onChangeText={(value) => updateItemField(item.id, { description: value })}
                      style={styles.input}
                      placeholder="Descripcion"
                    />
                    <TextInput
                      value={item.amountInput}
                      onChangeText={(value) => updateItemField(item.id, { amountInput: value })}
                      style={styles.input}
                      keyboardType="decimal-pad"
                      placeholder="0.00"
                    />
                    <Text style={styles.modalLabel}>Usuarios de esta linea</Text>
                    <ScrollView horizontal showsHorizontalScrollIndicator={false}>
                      <View style={styles.tags}>
                        {availableMembers
                          .filter((member) => expenseParticipants.includes(member.id))
                          .map((member) => {
                            const selected = item.participants.includes(member.id);
                            return (
                              <Pressable
                                key={`${item.id}-${member.id}`}
                                style={[styles.tag, selected ? styles.tagOn : null]}
                                onPress={() => toggleItemParticipant(item.id, member.id)}
                              >
                                <Text style={[styles.tagTx, selected ? styles.tagTxOn : null]}>{member.name}</Text>
                              </Pressable>
                            );
                          })}
                      </View>
                    </ScrollView>
                    <Pressable style={styles.removeItemBtn} onPress={() => removeItem(item.id)}>
                      <Text style={styles.removeItemBtnText}>Eliminar linea</Text>
                    </Pressable>
                  </View>
                ))}
                {items.length === 0 ? <Text style={styles.subtle}>No hay lineas. Anade al menos una.</Text> : null}
              </ScrollView>

              <View style={styles.row}>
                <Pressable style={styles.softBtn} onPress={() => setStep('upload')}><Text style={styles.softBtnText}>Reintentar</Text></Pressable>
                <Pressable style={styles.mainBtn} onPress={save} disabled={loading}>
                  {loading ? <ActivityIndicator color="#fff" /> : <Text style={styles.mainBtnText}>Guardar</Text>}
                </Pressable>
              </View>
            </>
          ) : null}
          {error ? <Text style={styles.err}>{error}</Text> : null}
          <Pressable onPress={close}><Text style={styles.close}>Cerrar</Text></Pressable>
        </View>
      </View>
    </Modal>
  );
}

function GroupDetailModal({
  open,
  detail,
  loading,
  onClose,
  onRefresh,
  onAddExpense,
}: {
  open: boolean;
  detail: GroupDetailData | null;
  loading: boolean;
  onClose: () => void;
  onRefresh: () => Promise<void>;
  onAddExpense: () => void;
}) {
  return (
    <Modal visible={open} transparent animationType="slide" onRequestClose={onClose}>
      <View style={styles.modalOverlay}>
        <View style={styles.modalCard}>
          <View style={styles.panelRow}>
            <Text style={styles.modalTitle}>{detail?.name || 'Grupo'}</Text>
            <Text style={styles.subtle}>Codigo: {detail?.code || '-'}</Text>
          </View>

          <View style={styles.row}>
            <Pressable
              style={styles.softBtn}
              onPress={() => {
                void onRefresh();
              }}
              disabled={loading}
            >
              <Text style={styles.softBtnText}>{loading ? 'Actualizando...' : 'Actualizar'}</Text>
            </Pressable>
            <Pressable style={styles.mainBtn} onPress={onAddExpense}>
              <Text style={styles.mainBtnText}>Anadir gasto</Text>
            </Pressable>
          </View>

          {loading ? (
            <View style={styles.processing}>
              <ActivityIndicator size="small" color="#10b981" />
              <Text style={styles.subtle}>Cargando detalle del grupo...</Text>
            </View>
          ) : (
            <ScrollView style={{ maxHeight: 420 }}>
              <Text style={styles.modalLabel}>Miembros</Text>
              <View style={styles.panel}>
                {detail?.members.length ? (
                  detail.members.map((member) => (
                    <View key={member.id} style={styles.groupRow}>
                      <Text style={styles.groupTitle}>{member.name}</Text>
                      <Text style={styles.subtle}>{member.email || `#${member.id}`}</Text>
                    </View>
                  ))
                ) : (
                  <Text style={styles.subtle}>Este grupo no tiene miembros.</Text>
                )}
              </View>

              <Text style={styles.modalLabel}>Balances</Text>
              <View style={styles.panel}>
                {detail?.balances.length ? (
                  detail.balances.map((b, i) => (
                    <View key={`${b.from}-${b.to}-${i}`} style={styles.groupCol}>
                      <Text style={styles.groupTitle}>{b.from} paga a {b.to}</Text>
                      <Text style={styles.subtle}>{b.groupName}</Text>
                      <Text style={styles.groupCode}>{money(b.amount)}</Text>
                    </View>
                  ))
                ) : (
                  <Text style={styles.subtle}>Sin balances pendientes.</Text>
                )}
              </View>

              <Text style={styles.modalLabel}>Gastos recientes</Text>
              <View style={styles.panel}>
                {detail?.expenses.length ? (
                  detail.expenses.map((expense) => (
                    <View key={expense.id} style={styles.groupCol}>
                      <Text style={styles.groupTitle}>{expense.title}</Text>
                      <Text style={styles.subtle}>{formatExpenseDate(expense.date)}</Text>
                      <Text style={styles.groupCode}>{money(expense.totalAmount)}</Text>
                    </View>
                  ))
                ) : (
                  <Text style={styles.subtle}>No hay gastos en este grupo.</Text>
                )}
              </View>
            </ScrollView>
          )}

          <Pressable onPress={onClose}>
            <Text style={styles.close}>Cerrar</Text>
          </Pressable>
        </View>
      </View>
    </Modal>
  );
}

export default function App() {
  const [user, setUser] = useState<AppUser | null>(null);
  const [email, setEmail] = useState('');
  const [name, setName] = useState('');
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [authError, setAuthError] = useState('');
  const [authLoading, setAuthLoading] = useState(false);

  const [tab, setTab] = useState<TabKey>('home');
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const [expenseOpen, setExpenseOpen] = useState(false);
  const [expensePresetGroupId, setExpensePresetGroupId] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
  const [users, setUsers] = useState<AppUser[]>([]);
  const [groups, setGroups] = useState<AppGroup[]>([]);
  const [summary, setSummary] = useState<any>(null);
  const [pyg, setPyg] = useState<Array<{ category: string; amount: number }>>([]);
  const [balances, setBalances] = useState<BalanceTransfer[]>([]);
  const [groupDetailOpen, setGroupDetailOpen] = useState(false);
  const [groupDetailLoading, setGroupDetailLoading] = useState(false);
  const [selectedGroupId, setSelectedGroupId] = useState<number | null>(null);
  const [groupDetail, setGroupDetail] = useState<GroupDetailData | null>(null);
  const statusInset = Platform.OS === 'android' ? (StatusBar.currentHeight || 0) : 0;

  const personal = useMemo(() => pyg.reduce((a, c) => a + Number(c.amount || 0), 0), [pyg]);

  const openGroupDetail = async (groupId: number) => {
    setSelectedGroupId(groupId);
    setGroupDetailOpen(true);
    setGroupDetailLoading(true);
    try {
      const [groupData, balancesData, expensesData] = await Promise.all([
        apiService.groups.get(String(groupId)),
        apiService.groups.getBalances(String(groupId)),
        apiService.groups.getExpenses(String(groupId)),
      ]);

      const members = Array.isArray(groupData?.members)
        ? groupData.members
            .map((member: any) => ({
              id: Number(member?.id),
              name: String(member?.name || `Usuario ${member?.id}`),
              email: typeof member?.email === 'string' ? member.email : '',
            }))
            .filter((member: AppUser) => Number.isFinite(member.id) && member.id > 0)
        : [];

      const expenses = Array.isArray(expensesData)
        ? expensesData
            .map((expense: any) => ({
              id: Number(expense?.id),
              title: String(expense?.title || expense?.merchant_name || 'Gasto'),
              totalAmount: Number(expense?.total_amount || expense?.totalAmount || 0),
              date: String(expense?.date || ''),
            }))
            .filter((expense: AppExpensePreview) => Number.isFinite(expense.id) && expense.id > 0)
        : [];

      const groupName = String(groupData?.name || groups.find((g) => g.id === groupId)?.name || 'Grupo');
      const groupCode = String(groupData?.code || groupData?.join_code || groups.find((g) => g.id === groupId)?.code || '');

      const detailBalances = Array.isArray(balancesData)
        ? balancesData.map((entry: any) => ({
            from: String(entry?.from || ''),
            to: String(entry?.to || ''),
            amount: Number(entry?.amount || 0),
            groupName,
          }))
        : [];

      setGroupDetail({
        groupId,
        name: groupName,
        code: groupCode,
        members,
        balances: detailBalances,
        expenses,
      });
    } catch (e: any) {
      Alert.alert('No se pudo abrir el grupo', e?.message || 'Error cargando el detalle del grupo.');
      setGroupDetailOpen(false);
    } finally {
      setGroupDetailLoading(false);
    }
  };

  const refreshGroupDetail = async () => {
    if (!selectedGroupId) return;
    await openGroupDetail(selectedGroupId);
  };

  const logout = () => {
    setUser(null);
    setEmail('');
    setName('');
    setMode('login');
    setAuthError('');
    setTab('home');
    setDrawerOpen(false);
    setCreateOpen(false);
    setExpenseOpen(false);
    setExpensePresetGroupId(null);
    setGroupDetailOpen(false);
    setGroupDetail(null);
    setSelectedGroupId(null);
    setGroups([]);
    setSummary(null);
    setPyg([]);
    setBalances([]);
  };

  const loadAll = async (userId: number) => {
    setLoading(true);
    try {
      const [usersData, groupsData, summaryData, pygData] = await Promise.all([
        apiService.users.list(),
        apiService.groups.list(),
        apiService.summary.get(String(userId)),
        apiService.pyg.get(userId),
      ]);
      setUsers(usersData.map((u) => ({ id: Number(u.id), name: String(u.name), email: String(u.email || '') })));
      const normalizedGroups = groupsData.map((g) => ({ id: Number(g.id), name: String(g.name), code: String(g.code || g.join_code || '') }));
      setGroups(normalizedGroups);
      setSummary(summaryData);
      setPyg((pygData || []).map((r: any) => ({ category: String(r.category || 'Otros'), amount: Number(r.amount || 0) })));

      const rows = await Promise.all(
        normalizedGroups.map(async (g) =>
          (await apiService.groups.getBalances(String(g.id))).map((it: any) => ({
            from: String(it.from),
            to: String(it.to),
            amount: Number(it.amount || 0),
            groupName: g.name,
          })),
        ),
      );
      setBalances(rows.flat());
    } finally {
      setLoading(false);
    }
  };

  const auth = async () => {
    if (!email.trim()) return setAuthError('Introduce email');
    if (mode === 'register' && !name.trim()) return setAuthError('Introduce nombre');
    setAuthLoading(true);
    setAuthError('');
    try {
      const r = mode === 'login' ? await apiService.auth.login(email.trim()) : await apiService.auth.register(email.trim(), name.trim());
      const me = { id: Number(r.id), name: String(r.name || name || email), email: String(r.email || email) };
      setUser(me);
      await loadAll(me.id);
    } catch (e: any) {
      setAuthError(e?.message || 'Error autenticando');
    } finally {
      setAuthLoading(false);
    }
  };

  if (!user) {
    return (
      <SafeAreaView style={[styles.screenRoot, { paddingTop: statusInset }]}>
        <StatusBar barStyle="dark-content" backgroundColor="#f3f4f6" translucent={false} />
        <View style={styles.authCard}>
          <Text style={styles.heading}>SplitScan</Text>
          {mode === 'register' ? <TextInput value={name} onChangeText={setName} style={styles.input} placeholder="Nombre" /> : null}
          <TextInput value={email} onChangeText={setEmail} style={styles.input} placeholder="Email" autoCapitalize="none" />
          {authError ? <Text style={styles.err}>{authError}</Text> : null}
          <Pressable style={styles.mainBtn} onPress={auth} disabled={authLoading}>
            {authLoading ? <ActivityIndicator color="#fff" /> : <Text style={styles.mainBtnText}>{mode === 'login' ? 'Entrar' : 'Crear cuenta'}</Text>}
          </Pressable>
          <Pressable onPress={() => setMode((m) => (m === 'login' ? 'register' : 'login'))}><Text style={styles.close}>{mode === 'login' ? 'No tengo cuenta' : 'Ya tengo cuenta'}</Text></Pressable>
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={[styles.screenRoot, { paddingTop: statusInset }]}>
      <StatusBar barStyle="dark-content" backgroundColor="#f3f4f6" translucent={false} />
      <View style={styles.header}>
        <Pressable style={styles.iconBtn} onPress={() => setDrawerOpen(true)}><Feather name="menu" size={18} color="#9ca3af" /></Pressable>
        <Text style={styles.headerTitle}>SplitScan</Text>
        <Pressable style={styles.iconBtn} onPress={() => loadAll(user.id)}><Feather name="refresh-cw" size={16} color="#9ca3af" /></Pressable>
      </View>

      {loading ? <View style={styles.fill}><ActivityIndicator size="large" color="#10b981" /></View> : null}
      {!loading && tab === 'home' ? (
        <ScrollView contentContainerStyle={styles.content}>
          <Text style={styles.kicker}>HOLA, {user.name.toUpperCase()}</Text>
          <Text style={styles.bigTitle}>Tu Resumen</Text>
          <View style={styles.cards}>
            <View style={[styles.balanceCard, { borderColor: '#d1fae5' }]}><Text style={styles.green}>Te deben</Text><Text style={styles.greenAmt}>{money(summary?.toReceive || 0)}</Text></View>
            <View style={[styles.balanceCard, { borderColor: '#fecaca' }]}><Text style={styles.red}>Debes</Text><Text style={styles.redAmt}>{money(summary?.toPay || 0)}</Text></View>
          </View>
          <View style={styles.panel}>
            <View style={styles.panelRow}><Text style={styles.panelTitle}>Tus Grupos</Text><Pressable onPress={() => setTab('groups')}><Text style={styles.link}>Ver todos</Text></Pressable></View>
            {groups.length === 0 ? (
              <Text style={styles.subtle}>No tienes grupos</Text>
            ) : (
              groups.map((g) => (
                <Pressable key={g.id} style={styles.groupRow} onPress={() => { void openGroupDetail(g.id); }}>
                  <Text style={styles.groupTitle}>{g.name}</Text>
                  <Text style={styles.groupCode}>{g.code}</Text>
                </Pressable>
              ))
            )}
          </View>
        </ScrollView>
      ) : null}
      {!loading && tab === 'groups' ? (
        <ScrollView contentContainerStyle={styles.content}>
          <View style={styles.panelRow}><Text style={styles.bigTitle}>Tus Grupos</Text><Pressable onPress={() => setCreateOpen(true)} style={styles.plusMini}><Feather name="plus" size={20} color="#10b981" /></Pressable></View>
          <View style={styles.panel}>
            {groups.length === 0 ? (
              <Text style={styles.subtle}>Aun no tienes grupos</Text>
            ) : (
              groups.map((g) => (
                <Pressable key={g.id} style={styles.groupRow} onPress={() => { void openGroupDetail(g.id); }}>
                  <Text style={styles.groupTitle}>{g.name}</Text>
                  <Text style={styles.groupCode}>{g.code}</Text>
                </Pressable>
              ))
            )}
          </View>
        </ScrollView>
      ) : null}
      {!loading && tab === 'spending' ? (
        <ScrollView contentContainerStyle={styles.content}>
          <Text style={styles.kicker}>GASTO PERSONAL REAL</Text>
          <Text style={styles.bigTitle}>{money(personal)}</Text>
          <Text style={styles.subtle}>Calculado tras divisiones y deudas.</Text>
          <View style={styles.panel}>
            <View style={styles.panelRow}><Text style={styles.panelTitle}>Por Categoria</Text><Text style={styles.link}>Este mes</Text></View>
            {pyg.map((r) => <View key={r.category} style={styles.groupRow}><Text style={styles.groupTitle}>{r.category}</Text><Text style={styles.groupCode}>{money(r.amount)}</Text></View>)}
            <Text style={styles.panelTitle}>Actividad Reciente</Text>
            {(summary?.recentExpenses || []).map((e: any) => <View key={String(e.id)} style={styles.groupRow}><Text style={styles.groupTitle}>{e.title}</Text><Text style={styles.groupCode}>{money(e.personalAmount || e.totalAmount || 0)}</Text></View>)}
          </View>
        </ScrollView>
      ) : null}
      {!loading && tab === 'balance' ? (
        <ScrollView contentContainerStyle={styles.content}>
          <Text style={styles.bigTitle}>Balance</Text>
          <View style={styles.panel}>
            {balances.length === 0 ? <Text style={styles.subtle}>Sin balances pendientes</Text> : balances.map((b, i) => <View key={`${b.from}-${b.to}-${i}`} style={styles.groupCol}><Text style={styles.groupTitle}>{b.from} paga a {b.to}</Text><Text style={styles.subtle}>{b.groupName}</Text><Text style={styles.groupCode}>{money(b.amount)}</Text></View>)}
          </View>
          <View style={styles.row}>
            <Pressable style={styles.softBtn} onPress={() => loadAll(user.id)}>
              <Text style={styles.softBtnText}>Actualizar</Text>
            </Pressable>
            <Pressable style={[styles.softBtn, styles.logoutBtn]} onPress={logout}>
              <Text style={styles.logoutBtnText}>Cerrar sesion</Text>
            </Pressable>
          </View>
        </ScrollView>
      ) : null}

      <View style={styles.bottom}>
        <TabButton icon="grid" label="INICIO" active={tab === 'home'} onPress={() => setTab('home')} />
        <TabButton icon="users" label="GRUPOS" active={tab === 'groups'} onPress={() => setTab('groups')} />
        <View style={{ width: 70 }} />
        <TabButton icon="trending-up" label="GASTOS" active={tab === 'spending'} onPress={() => setTab('spending')} />
        <TabButton icon="repeat" label="BALANCE" active={tab === 'balance'} onPress={() => setTab('balance')} />
      </View>
      <Pressable
        style={styles.plus}
        onPress={() => {
          setExpensePresetGroupId(null);
          setExpenseOpen(true);
        }}
      >
        <Feather name="plus" size={34} color="#fff" />
      </Pressable>

      <Drawer
        open={drawerOpen}
        active={tab}
        topInset={statusInset}
        onClose={() => setDrawerOpen(false)}
        onSelect={setTab}
      />
      <CreateGroupModal
        open={createOpen}
        users={users}
        me={user.id}
        onClose={() => setCreateOpen(false)}
        onCreate={async (groupName, memberIds) => {
          await apiService.groups.create({ name: groupName, userId: user.id, memberIds });
          await loadAll(user.id);
        }}
      />
      <AddExpenseModal
        open={expenseOpen}
        groups={groups}
        me={user.id}
        meName={user.name}
        initialGroupId={expensePresetGroupId}
        onClose={() => {
          setExpenseOpen(false);
          setExpensePresetGroupId(null);
        }}
        onCreated={() => loadAll(user.id)}
      />
      <GroupDetailModal
        open={groupDetailOpen}
        detail={groupDetail}
        loading={groupDetailLoading}
        onClose={() => setGroupDetailOpen(false)}
        onRefresh={refreshGroupDetail}
        onAddExpense={() => {
          setGroupDetailOpen(false);
          setExpensePresetGroupId(selectedGroupId);
          setExpenseOpen(true);
        }}
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  screenRoot: { flex: 1, backgroundColor: '#f3f4f6' },
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 16, paddingVertical: 8 },
  headerTitle: { color: '#0b1f3a', fontWeight: '700', fontSize: 18 },
  iconBtn: { width: 36, height: 36, borderRadius: 18, backgroundColor: '#e5e7eb', alignItems: 'center', justifyContent: 'center' },
  fill: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  content: { paddingHorizontal: 18, paddingBottom: 120, gap: 12 },
  kicker: { color: '#94a3b8', fontWeight: '700', letterSpacing: 1.2, fontSize: 12 },
  bigTitle: { color: '#0b1f3a', fontWeight: '700', fontSize: 40 },
  cards: { flexDirection: 'row', gap: 10 },
  balanceCard: { flex: 1, backgroundColor: '#fff', borderWidth: 1, borderRadius: 16, padding: 14 },
  green: { color: '#059669', fontWeight: '600', fontSize: 16 },
  greenAmt: { color: '#064e3b', fontWeight: '700', fontSize: 28, marginTop: 2 },
  red: { color: '#dc2626', fontWeight: '600', fontSize: 16 },
  redAmt: { color: '#7f1d1d', fontWeight: '700', fontSize: 28, marginTop: 2 },
  panel: { backgroundColor: '#eef0f3', padding: 16, gap: 12 },
  panelRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  panelTitle: { color: '#0b1f3a', fontWeight: '700', fontSize: 34 - 8 },
  link: { color: '#10b981', fontWeight: '700', fontSize: 18 - 1 },
  subtle: { color: '#64748b', fontSize: 16 },
  groupRow: { backgroundColor: '#fff', borderRadius: 14, borderWidth: 1, borderColor: '#e5e7eb', padding: 12, flexDirection: 'row', justifyContent: 'space-between' },
  groupCol: { backgroundColor: '#fff', borderRadius: 14, borderWidth: 1, borderColor: '#e5e7eb', padding: 12, gap: 4 },
  groupTitle: { color: '#0b1f3a', fontWeight: '700', fontSize: 18 },
  groupCode: { color: '#0b1f3a', fontWeight: '700', fontSize: 18 },
  bottom: { position: 'absolute', left: 0, right: 0, bottom: 0, height: 90, backgroundColor: '#fff', borderTopColor: '#e5e7eb', borderTopWidth: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-around' },
  tabButton: { width: 66, alignItems: 'center', gap: 3 },
  tabText: { color: '#9ca3af', fontWeight: '700', fontSize: 12 },
  tabTextActive: { color: '#10b981' },
  plus: { position: 'absolute', bottom: 47, alignSelf: 'center', width: 76, height: 76, borderRadius: 38, backgroundColor: '#10b981', alignItems: 'center', justifyContent: 'center', borderWidth: 4, borderColor: '#ecfdf5' },
  drawerOverlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.3)' },
  drawerPanel: { width: 230, height: '100%', backgroundColor: '#fff', paddingTop: 56, paddingHorizontal: 14 },
  drawerTitle: { color: '#0b1f3a', fontWeight: '700', fontSize: 22, marginBottom: 8 },
  drawerItem: { backgroundColor: '#f3f4f6', borderRadius: 10, padding: 10, marginBottom: 6 },
  drawerItemActive: { backgroundColor: '#10b981' },
  drawerItemText: { color: '#0b1f3a', fontWeight: '600', fontSize: 16 },
  drawerItemTextActive: { color: '#fff' },
  modalOverlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.35)', justifyContent: 'flex-end' },
  modalCard: { backgroundColor: '#fff', borderTopLeftRadius: 20, borderTopRightRadius: 20, padding: 16, gap: 10, maxHeight: '90%' },
  modalTitle: { color: '#0b1f3a', fontWeight: '700', fontSize: 24 },
  modalLabel: { color: '#64748b', fontSize: 13, fontWeight: '700' },
  processingBadge: { alignSelf: 'flex-start', borderRadius: 999, paddingHorizontal: 12, paddingVertical: 7 },
  processingBadgeText: { fontSize: 12, fontWeight: '800' },
  processingBadgeDonut: { backgroundColor: '#dcfce7' },
  processingBadgeTextDonut: { color: '#166534' },
  processingBadgeManual: { backgroundColor: '#f3f4f6' },
  processingBadgeTextManual: { color: '#374151' },
  input: { borderWidth: 1, borderColor: '#e5e7eb', borderRadius: 12, backgroundColor: '#fff', paddingHorizontal: 12, paddingVertical: 10, color: '#0b1f3a' },
  userRow: { backgroundColor: '#f3f4f6', borderRadius: 10, padding: 10, marginBottom: 6 },
  userRowActive: { backgroundColor: '#d1fae5' },
  userName: { color: '#0b1f3a', fontWeight: '700' },
  userMail: { color: '#64748b', fontSize: 12 },
  row: { flexDirection: 'row', gap: 8 },
  softBtn: { flex: 1, backgroundColor: '#ecfdf5', borderRadius: 10, paddingVertical: 11, alignItems: 'center' },
  softBtnText: { color: '#059669', fontWeight: '700' },
  logoutBtn: { backgroundColor: '#fee2e2' },
  logoutBtnText: { color: '#b91c1c', fontWeight: '700' },
  softMiniBtn: { backgroundColor: '#ecfdf5', borderRadius: 10, paddingHorizontal: 10, paddingVertical: 7 },
  softMiniBtnText: { color: '#059669', fontWeight: '700', fontSize: 12 },
  mainBtn: { flex: 1, backgroundColor: '#10b981', borderRadius: 10, paddingVertical: 11, alignItems: 'center' },
  mainBtnText: { color: '#fff', fontWeight: '700' },
  preview: { height: 160, borderWidth: 1, borderColor: '#e5e7eb', borderRadius: 12, alignItems: 'center', justifyContent: 'center', backgroundColor: '#f8fafc', overflow: 'hidden' },
  previewImg: { width: '100%', height: '100%' },
  tags: { flexDirection: 'row', gap: 8 },
  tag: { backgroundColor: '#f3f4f6', paddingHorizontal: 12, paddingVertical: 8, borderRadius: 999 },
  tagOn: { backgroundColor: '#10b981' },
  tagTx: { color: '#0b1f3a', fontWeight: '700', fontSize: 12 },
  tagTxOn: { color: '#fff' },
  itemCard: { borderWidth: 1, borderColor: '#e5e7eb', borderRadius: 12, padding: 10, backgroundColor: '#f8fafc', gap: 8, marginBottom: 8 },
  removeItemBtn: { alignSelf: 'flex-end', backgroundColor: '#fee2e2', paddingHorizontal: 10, paddingVertical: 6, borderRadius: 8 },
  removeItemBtnText: { color: '#b91c1c', fontWeight: '700', fontSize: 12 },
  processing: { alignItems: 'center', justifyContent: 'center', paddingVertical: 30, gap: 8 },
  reviewTotal: { color: '#0b1f3a', fontWeight: '700', fontSize: 36, textAlign: 'center' },
  err: { color: '#b91c1c', fontSize: 12 },
  close: { color: '#64748b', textAlign: 'center', marginTop: 4, fontWeight: '600' },
  authCard: { marginTop: 100, marginHorizontal: 20, backgroundColor: '#fff', borderRadius: 18, padding: 16, gap: 10 },
  heading: { color: '#0b1f3a', fontSize: 30, fontWeight: '700' },
  plusMini: { width: 46, height: 46, borderRadius: 23, backgroundColor: '#d1fae5', alignItems: 'center', justifyContent: 'center' },
});
