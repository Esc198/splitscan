package com.splitscan.RestAPI.Services;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyList;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.inOrder;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.Optional;
import java.util.UUID;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Captor;
import org.mockito.InjectMocks;
import org.mockito.InOrder;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.http.HttpStatus;
import org.springframework.web.server.ResponseStatusException;

import com.splitscan.RestAPI.DTOs.transaction.TransactionRequestDTO;
import com.splitscan.RestAPI.DTOs.transaction.TransactionResponseDTO;
import com.splitscan.RestAPI.Models.Group;
import com.splitscan.RestAPI.Models.GroupMember;
import com.splitscan.RestAPI.Models.Transaction;
import com.splitscan.RestAPI.Models.TransactionSplit;
import com.splitscan.RestAPI.Models.User;
import com.splitscan.RestAPI.Repositories.GroupMemberRepository;
import com.splitscan.RestAPI.Repositories.GroupRepository;
import com.splitscan.RestAPI.Repositories.TransactionRepository;
import com.splitscan.RestAPI.Repositories.TransactionSplitRepository;

@ExtendWith(MockitoExtension.class)
class TransactionServiceTest {

    @Mock
    private GroupRepository groupRepository;

    @Mock
    private GroupMemberRepository groupMemberRepository;

    @Mock
    private TransactionRepository transactionRepository;

    @Mock
    private TransactionSplitRepository transactionSplitRepository;

    @InjectMocks
    private TransactionService transactionService;

    @Captor
    private ArgumentCaptor<Transaction> transactionCaptor;

    @Captor
    private ArgumentCaptor<List<TransactionSplit>> splitsCaptor;

    @Test
    void getTransactionsWithoutSinceReturnsActiveTransactionsOrderedByUpdatedAtAsc() {
        UUID currentUserId = UUID.randomUUID();
        UUID groupId = UUID.randomUUID();
        Group group = buildGroup(groupId, "Viaje");
        User payer = buildUser(UUID.randomUUID(), "Enrique", "enrique@example.com");
        User participant = buildUser(UUID.randomUUID(), "Laura", "laura@example.com");
        Transaction first = buildTransaction(
                UUID.randomUUID(),
                group,
                payer,
                "Taxi",
                "20.00",
                "2026-03-16T08:00:00Z",
                "2026-03-16T08:05:00Z",
                null);
        Transaction second = buildTransaction(
                UUID.randomUUID(),
                group,
                payer,
                "Cena",
                "50.00",
                "2026-03-16T09:00:00Z",
                "2026-03-16T09:10:00Z",
                null);

        when(groupRepository.findById(groupId)).thenReturn(Optional.of(group));
        when(groupMemberRepository.existsByGroup_IdAndUser_Id(groupId, currentUserId)).thenReturn(true);
        when(transactionRepository.findByGroup_IdAndDeletedAtIsNullOrderByUpdatedAtAsc(groupId))
                .thenReturn(List.of(first, second));
        when(transactionSplitRepository.findByTransaction_IdInOrderByTransaction_IdAscUser_IdAsc(
                List.of(first.getId(), second.getId())))
                        .thenReturn(List.of(
                                buildSplit(first, payer, "10.00"),
                                buildSplit(first, participant, "10.00"),
                                buildSplit(second, payer, "25.00"),
                                buildSplit(second, participant, "25.00")));

        List<TransactionResponseDTO> response = transactionService.getTransactions(currentUserId, groupId, null);

        assertEquals(List.of(first.getId(), second.getId()), response.stream().map(TransactionResponseDTO::getId).toList());
        assertEquals(2, response.get(0).getSplits().size());
        assertEquals(2, response.get(1).getSplits().size());
        verify(transactionRepository, never()).findByGroup_IdAndUpdatedAtGreaterThanEqualOrderByUpdatedAtAsc(any(), any());
    }

    @Test
    void getTransactionsFailsWhenCurrentUserIsNotMember() {
        UUID currentUserId = UUID.randomUUID();
        UUID groupId = UUID.randomUUID();
        Group group = buildGroup(groupId, "Viaje");

        when(groupRepository.findById(groupId)).thenReturn(Optional.of(group));
        when(groupMemberRepository.existsByGroup_IdAndUser_Id(groupId, currentUserId)).thenReturn(false);

        ResponseStatusException ex = assertThrows(ResponseStatusException.class,
                () -> transactionService.getTransactions(currentUserId, groupId, null));

        assertEquals(HttpStatus.FORBIDDEN, ex.getStatusCode());
        verify(transactionRepository, never()).findByGroup_IdAndDeletedAtIsNullOrderByUpdatedAtAsc(groupId);
    }

    @Test
    void getTransactionsSinceReturnsUpdatedTransactionsIncludingDeleted() {
        UUID currentUserId = UUID.randomUUID();
        UUID groupId = UUID.randomUUID();
        Instant since = Instant.parse("2026-03-16T10:00:00Z");
        Group group = buildGroup(groupId, "Viaje");
        User payer = buildUser(UUID.randomUUID(), "Enrique", "enrique@example.com");
        Transaction active = buildTransaction(
                UUID.randomUUID(),
                group,
                payer,
                "Comida",
                "30.00",
                "2026-03-16T09:00:00Z",
                "2026-03-16T10:05:00Z",
                null);
        Transaction deleted = buildTransaction(
                UUID.randomUUID(),
                group,
                payer,
                "Hotel",
                "100.00",
                "2026-03-16T09:30:00Z",
                "2026-03-16T10:15:00Z",
                "2026-03-16T10:15:00Z");

        when(groupRepository.findById(groupId)).thenReturn(Optional.of(group));
        when(groupMemberRepository.existsByGroup_IdAndUser_Id(groupId, currentUserId)).thenReturn(true);
        when(transactionRepository.findByGroup_IdAndUpdatedAtGreaterThanEqualOrderByUpdatedAtAsc(groupId, since))
                .thenReturn(List.of(active, deleted));
        when(transactionSplitRepository.findByTransaction_IdInOrderByTransaction_IdAscUser_IdAsc(
                List.of(active.getId(), deleted.getId())))
                        .thenReturn(List.of(
                                buildSplit(active, payer, "30.00"),
                                buildSplit(deleted, payer, "100.00")));

        List<TransactionResponseDTO> response = transactionService.getTransactions(currentUserId, groupId, since);

        assertEquals(2, response.size());
        assertNull(response.get(0).getDeletedAt());
        assertEquals(Instant.parse("2026-03-16T10:15:00Z"), response.get(1).getDeletedAt());
    }

    @Test
    void getTransactionReturnsActiveTransactionWithSplits() {
        UUID currentUserId = UUID.randomUUID();
        UUID groupId = UUID.randomUUID();
        UUID transactionId = UUID.randomUUID();
        Group group = buildGroup(groupId, "Viaje");
        User payer = buildUser(UUID.randomUUID(), "Enrique", "enrique@example.com");
        User participant = buildUser(UUID.randomUUID(), "Laura", "laura@example.com");
        Transaction transaction = buildTransaction(
                transactionId,
                group,
                payer,
                "Cena",
                "60.00",
                "2026-03-16T10:00:00Z",
                "2026-03-16T10:00:00Z",
                null);

        when(groupRepository.findById(groupId)).thenReturn(Optional.of(group));
        when(groupMemberRepository.existsByGroup_IdAndUser_Id(groupId, currentUserId)).thenReturn(true);
        when(transactionRepository.findByIdAndGroup_IdAndDeletedAtIsNull(transactionId, groupId))
                .thenReturn(Optional.of(transaction));
        when(transactionSplitRepository.findByTransaction_IdInOrderByTransaction_IdAscUser_IdAsc(List.of(transactionId)))
                .thenReturn(List.of(
                        buildSplit(transaction, participant, "20.00"),
                        buildSplit(transaction, payer, "40.00")));

        TransactionResponseDTO response = transactionService.getTransaction(currentUserId, groupId, transactionId);

        assertEquals(transactionId, response.getId());
        assertEquals(payer.getId(), response.getPaidByUserId());
        assertEquals(2, response.getSplits().size());
        assertEquals(
                List.of(participant.getId(), payer.getId()).stream().sorted().toList(),
                response.getSplits().stream().map(TransactionResponseDTO.SplitItem::getUserId).toList());
    }

    @Test
    void getTransactionFailsWhenTransactionDeletedOrMissing() {
        UUID currentUserId = UUID.randomUUID();
        UUID groupId = UUID.randomUUID();
        UUID transactionId = UUID.randomUUID();
        Group group = buildGroup(groupId, "Viaje");

        when(groupRepository.findById(groupId)).thenReturn(Optional.of(group));
        when(groupMemberRepository.existsByGroup_IdAndUser_Id(groupId, currentUserId)).thenReturn(true);
        when(transactionRepository.findByIdAndGroup_IdAndDeletedAtIsNull(transactionId, groupId))
                .thenReturn(Optional.empty());

        ResponseStatusException ex = assertThrows(ResponseStatusException.class,
                () -> transactionService.getTransaction(currentUserId, groupId, transactionId));

        assertEquals(HttpStatus.NOT_FOUND, ex.getStatusCode());
    }

    @Test
    void createTransactionPersistsTransactionAndSplits() {
        UUID currentUserId = UUID.randomUUID();
        UUID groupId = UUID.randomUUID();
        Group group = buildGroup(groupId, "Viaje");
        User payer = buildUser(UUID.randomUUID(), "Enrique", "enrique@example.com");
        User participant = buildUser(UUID.randomUUID(), "Laura", "laura@example.com");
        TransactionRequestDTO request = buildRequest(
                payer.getId(),
                "60.00",
                splitItem(payer.getId(), "30.00"),
                splitItem(participant.getId(), "30.00"));

        when(groupRepository.findById(groupId)).thenReturn(Optional.of(group));
        when(groupMemberRepository.existsByGroup_IdAndUser_Id(groupId, currentUserId)).thenReturn(true);
        when(groupMemberRepository.findByGroup_Id(groupId))
                .thenReturn(List.of(buildMember(group, payer), buildMember(group, participant)));
        when(transactionRepository.save(any(Transaction.class)))
                .thenAnswer(invocation -> invocation.getArgument(0));
        when(transactionSplitRepository.saveAll(anyList()))
                .thenAnswer(invocation -> copySplits(invocation.getArgument(0)));

        TransactionResponseDTO response = transactionService.createTransaction(currentUserId, groupId, request);

        verify(transactionRepository).save(transactionCaptor.capture());
        Transaction savedTransaction = transactionCaptor.getValue();
        assertNotNull(savedTransaction.getId());
        assertEquals(groupId, savedTransaction.getGroup().getId());
        assertEquals(payer.getId(), savedTransaction.getPaidBy().getId());
        assertNotNull(savedTransaction.getCreatedAt());
        assertEquals(savedTransaction.getCreatedAt(), savedTransaction.getUpdatedAt());
        assertNull(savedTransaction.getDeletedAt());

        verify(transactionSplitRepository).saveAll(splitsCaptor.capture());
        List<TransactionSplit> savedSplits = splitsCaptor.getValue();
        assertEquals(2, savedSplits.size());
        assertTrue(savedSplits.stream().allMatch(split -> split.getTransaction().getId().equals(savedTransaction.getId())));
        assertEquals(savedTransaction.getId(), response.getId());
        assertEquals(2, response.getSplits().size());
    }

    @Test
    void createTransactionFailsWhenGroupMissing() {
        UUID currentUserId = UUID.randomUUID();
        UUID groupId = UUID.randomUUID();
        TransactionRequestDTO request = buildRequest(
                UUID.randomUUID(),
                "10.00",
                splitItem(UUID.randomUUID(), "10.00"));

        when(groupRepository.findById(groupId)).thenReturn(Optional.empty());

        ResponseStatusException ex = assertThrows(ResponseStatusException.class,
                () -> transactionService.createTransaction(currentUserId, groupId, request));

        assertEquals(HttpStatus.NOT_FOUND, ex.getStatusCode());
        verify(transactionRepository, never()).save(any(Transaction.class));
        verify(transactionSplitRepository, never()).saveAll(anyList());
    }

    @Test
    void createTransactionFailsWhenPaidByUserDoesNotBelongToGroup() {
        UUID currentUserId = UUID.randomUUID();
        UUID groupId = UUID.randomUUID();
        Group group = buildGroup(groupId, "Viaje");
        User currentUser = buildUser(currentUserId, "Current", "current@example.com");
        UUID outsiderId = UUID.randomUUID();
        TransactionRequestDTO request = buildRequest(
                outsiderId,
                "10.00",
                splitItem(currentUser.getId(), "10.00"));

        when(groupRepository.findById(groupId)).thenReturn(Optional.of(group));
        when(groupMemberRepository.existsByGroup_IdAndUser_Id(groupId, currentUserId)).thenReturn(true);
        when(groupMemberRepository.findByGroup_Id(groupId))
                .thenReturn(List.of(buildMember(group, currentUser)));

        ResponseStatusException ex = assertThrows(ResponseStatusException.class,
                () -> transactionService.createTransaction(currentUserId, groupId, request));

        assertEquals(HttpStatus.CONFLICT, ex.getStatusCode());
        verify(transactionRepository, never()).save(any(Transaction.class));
    }

    @Test
    void createTransactionFailsWhenSplitUserDoesNotBelongToGroup() {
        UUID currentUserId = UUID.randomUUID();
        UUID groupId = UUID.randomUUID();
        Group group = buildGroup(groupId, "Viaje");
        User payer = buildUser(currentUserId, "Enrique", "enrique@example.com");
        TransactionRequestDTO request = buildRequest(
                payer.getId(),
                "10.00",
                splitItem(UUID.randomUUID(), "10.00"));

        when(groupRepository.findById(groupId)).thenReturn(Optional.of(group));
        when(groupMemberRepository.existsByGroup_IdAndUser_Id(groupId, currentUserId)).thenReturn(true);
        when(groupMemberRepository.findByGroup_Id(groupId))
                .thenReturn(List.of(buildMember(group, payer)));

        ResponseStatusException ex = assertThrows(ResponseStatusException.class,
                () -> transactionService.createTransaction(currentUserId, groupId, request));

        assertEquals(HttpStatus.CONFLICT, ex.getStatusCode());
        verify(transactionRepository, never()).save(any(Transaction.class));
    }

    @Test
    void createTransactionFailsWhenRequestContainsDuplicateSplitUsers() {
        UUID currentUserId = UUID.randomUUID();
        UUID groupId = UUID.randomUUID();
        Group group = buildGroup(groupId, "Viaje");
        User payer = buildUser(currentUserId, "Enrique", "enrique@example.com");
        TransactionRequestDTO request = buildRequest(
                payer.getId(),
                "10.00",
                splitItem(payer.getId(), "5.00"),
                splitItem(payer.getId(), "5.00"));

        when(groupRepository.findById(groupId)).thenReturn(Optional.of(group));
        when(groupMemberRepository.existsByGroup_IdAndUser_Id(groupId, currentUserId)).thenReturn(true);
        when(groupMemberRepository.findByGroup_Id(groupId))
                .thenReturn(List.of(buildMember(group, payer)));

        ResponseStatusException ex = assertThrows(ResponseStatusException.class,
                () -> transactionService.createTransaction(currentUserId, groupId, request));

        assertEquals(HttpStatus.CONFLICT, ex.getStatusCode());
    }

    @Test
    void createTransactionFailsWhenRequestContainsNoSplits() {
        UUID currentUserId = UUID.randomUUID();
        UUID groupId = UUID.randomUUID();
        Group group = buildGroup(groupId, "Viaje");
        User payer = buildUser(currentUserId, "Enrique", "enrique@example.com");
        TransactionRequestDTO request = buildRequest(payer.getId(), "10.00");

        when(groupRepository.findById(groupId)).thenReturn(Optional.of(group));
        when(groupMemberRepository.existsByGroup_IdAndUser_Id(groupId, currentUserId)).thenReturn(true);

        ResponseStatusException ex = assertThrows(ResponseStatusException.class,
                () -> transactionService.createTransaction(currentUserId, groupId, request));

        assertEquals(HttpStatus.BAD_REQUEST, ex.getStatusCode());
        verify(groupMemberRepository, never()).findByGroup_Id(eq(groupId));
    }

    @Test
    void createTransactionFailsWhenSplitAmountsDoNotMatchTotal() {
        UUID currentUserId = UUID.randomUUID();
        UUID groupId = UUID.randomUUID();
        Group group = buildGroup(groupId, "Viaje");
        User payer = buildUser(currentUserId, "Enrique", "enrique@example.com");
        User participant = buildUser(UUID.randomUUID(), "Laura", "laura@example.com");
        TransactionRequestDTO request = buildRequest(
                payer.getId(),
                "10.00",
                splitItem(payer.getId(), "7.00"),
                splitItem(participant.getId(), "2.00"));

        when(groupRepository.findById(groupId)).thenReturn(Optional.of(group));
        when(groupMemberRepository.existsByGroup_IdAndUser_Id(groupId, currentUserId)).thenReturn(true);
        when(groupMemberRepository.findByGroup_Id(groupId))
                .thenReturn(List.of(buildMember(group, payer), buildMember(group, participant)));

        ResponseStatusException ex = assertThrows(ResponseStatusException.class,
                () -> transactionService.createTransaction(currentUserId, groupId, request));

        assertEquals(HttpStatus.BAD_REQUEST, ex.getStatusCode());
    }

    @Test
    void createTransactionFailsWhenAmountHasMoreThanTwoDecimals() {
        UUID currentUserId = UUID.randomUUID();
        UUID groupId = UUID.randomUUID();
        Group group = buildGroup(groupId, "Viaje");
        User payer = buildUser(currentUserId, "Enrique", "enrique@example.com");
        TransactionRequestDTO request = buildRequest(
                payer.getId(),
                "10.001",
                splitItem(payer.getId(), "10.001"));

        when(groupRepository.findById(groupId)).thenReturn(Optional.of(group));
        when(groupMemberRepository.existsByGroup_IdAndUser_Id(groupId, currentUserId)).thenReturn(true);

        ResponseStatusException ex = assertThrows(ResponseStatusException.class,
                () -> transactionService.createTransaction(currentUserId, groupId, request));

        assertEquals(HttpStatus.BAD_REQUEST, ex.getStatusCode());
        verify(groupMemberRepository, never()).findByGroup_Id(eq(groupId));
    }

    @Test
    void updateTransactionReplacesSplitsAndUpdatesUpdatedAt() {
        UUID currentUserId = UUID.randomUUID();
        UUID groupId = UUID.randomUUID();
        UUID transactionId = UUID.randomUUID();
        Group group = buildGroup(groupId, "Viaje");
        User oldPayer = buildUser(UUID.randomUUID(), "Enrique", "enrique@example.com");
        User newPayer = buildUser(currentUserId, "Laura", "laura@example.com");
        User thirdUser = buildUser(UUID.randomUUID(), "Marta", "marta@example.com");
        Transaction transaction = buildTransaction(
                transactionId,
                group,
                oldPayer,
                "Cena antigua",
                "30.00",
                "2026-03-16T09:00:00Z",
                "2026-03-16T09:05:00Z",
                null);
        Instant originalCreatedAt = transaction.getCreatedAt();
        Instant originalUpdatedAt = transaction.getUpdatedAt();
        TransactionRequestDTO request = buildRequest(
                newPayer.getId(),
                "45.00",
                splitItem(newPayer.getId(), "20.00"),
                splitItem(thirdUser.getId(), "25.00"));
        InOrder inOrder = inOrder(transactionRepository, transactionSplitRepository);

        when(groupRepository.findById(groupId)).thenReturn(Optional.of(group));
        when(groupMemberRepository.existsByGroup_IdAndUser_Id(groupId, currentUserId)).thenReturn(true);
        when(transactionRepository.findByIdAndGroup_IdAndDeletedAtIsNull(transactionId, groupId))
                .thenReturn(Optional.of(transaction));
        when(groupMemberRepository.findByGroup_Id(groupId))
                .thenReturn(List.of(
                        buildMember(group, oldPayer),
                        buildMember(group, newPayer),
                        buildMember(group, thirdUser)));
        when(transactionRepository.save(any(Transaction.class)))
                .thenAnswer(invocation -> invocation.getArgument(0));
        when(transactionSplitRepository.saveAll(anyList()))
                .thenAnswer(invocation -> copySplits(invocation.getArgument(0)));

        TransactionResponseDTO response = transactionService.updateTransaction(currentUserId, groupId, transactionId, request);

        inOrder.verify(transactionRepository).save(transactionCaptor.capture());
        inOrder.verify(transactionSplitRepository).deleteByTransaction_Id(transactionId);
        inOrder.verify(transactionSplitRepository).saveAll(splitsCaptor.capture());

        Transaction savedTransaction = transactionCaptor.getValue();
        assertEquals(originalCreatedAt, savedTransaction.getCreatedAt());
        assertTrue(savedTransaction.getUpdatedAt().isAfter(originalUpdatedAt));
        assertEquals(newPayer.getId(), savedTransaction.getPaidBy().getId());
        assertEquals(new BigDecimal("45.00"), savedTransaction.getAmount());
        assertEquals(2, splitsCaptor.getValue().size());
        assertEquals(transactionId, response.getId());
        assertEquals(newPayer.getId(), response.getPaidByUserId());
    }

    @Test
    void updateTransactionFailsWhenTransactionDeletedOrMissing() {
        UUID currentUserId = UUID.randomUUID();
        UUID groupId = UUID.randomUUID();
        UUID transactionId = UUID.randomUUID();
        Group group = buildGroup(groupId, "Viaje");
        TransactionRequestDTO request = buildRequest(
                UUID.randomUUID(),
                "10.00",
                splitItem(UUID.randomUUID(), "10.00"));

        when(groupRepository.findById(groupId)).thenReturn(Optional.of(group));
        when(groupMemberRepository.existsByGroup_IdAndUser_Id(groupId, currentUserId)).thenReturn(true);
        when(transactionRepository.findByIdAndGroup_IdAndDeletedAtIsNull(transactionId, groupId))
                .thenReturn(Optional.empty());

        ResponseStatusException ex = assertThrows(ResponseStatusException.class,
                () -> transactionService.updateTransaction(currentUserId, groupId, transactionId, request));

        assertEquals(HttpStatus.NOT_FOUND, ex.getStatusCode());
        verify(transactionSplitRepository, never()).deleteByTransaction_Id(transactionId);
    }

    @Test
    void deleteTransactionSetsDeletedAtAndUpdatedAt() {
        UUID currentUserId = UUID.randomUUID();
        UUID groupId = UUID.randomUUID();
        UUID transactionId = UUID.randomUUID();
        Group group = buildGroup(groupId, "Viaje");
        User payer = buildUser(UUID.randomUUID(), "Enrique", "enrique@example.com");
        Transaction transaction = buildTransaction(
                transactionId,
                group,
                payer,
                "Hotel",
                "100.00",
                "2026-03-16T10:00:00Z",
                "2026-03-16T10:05:00Z",
                null);

        when(groupRepository.findById(groupId)).thenReturn(Optional.of(group));
        when(groupMemberRepository.existsByGroup_IdAndUser_Id(groupId, currentUserId)).thenReturn(true);
        when(transactionRepository.findByIdAndGroup_IdAndDeletedAtIsNull(transactionId, groupId))
                .thenReturn(Optional.of(transaction));
        when(transactionRepository.save(any(Transaction.class)))
                .thenAnswer(invocation -> invocation.getArgument(0));

        transactionService.deleteTransaction(currentUserId, groupId, transactionId);

        verify(transactionRepository).save(transactionCaptor.capture());
        Transaction savedTransaction = transactionCaptor.getValue();
        assertNotNull(savedTransaction.getDeletedAt());
        assertEquals(savedTransaction.getDeletedAt(), savedTransaction.getUpdatedAt());
    }

    @Test
    void deleteTransactionFailsWhenTransactionDeletedOrMissing() {
        UUID currentUserId = UUID.randomUUID();
        UUID groupId = UUID.randomUUID();
        UUID transactionId = UUID.randomUUID();
        Group group = buildGroup(groupId, "Viaje");

        when(groupRepository.findById(groupId)).thenReturn(Optional.of(group));
        when(groupMemberRepository.existsByGroup_IdAndUser_Id(groupId, currentUserId)).thenReturn(true);
        when(transactionRepository.findByIdAndGroup_IdAndDeletedAtIsNull(transactionId, groupId))
                .thenReturn(Optional.empty());

        ResponseStatusException ex = assertThrows(ResponseStatusException.class,
                () -> transactionService.deleteTransaction(currentUserId, groupId, transactionId));

        assertEquals(HttpStatus.NOT_FOUND, ex.getStatusCode());
        verify(transactionRepository, never()).save(any(Transaction.class));
    }

    private Group buildGroup(UUID groupId, String name) {
        Group group = new Group();
        group.setId(groupId);
        group.setName(name);
        group.setCreatedAt(Instant.parse("2026-03-16T10:00:00Z"));
        return group;
    }

    private User buildUser(UUID userId, String name, String email) {
        User user = new User();
        user.setId(userId);
        user.setName(name);
        user.setEmail(email);
        return user;
    }

    private GroupMember buildMember(Group group, User user) {
        GroupMember member = new GroupMember();
        member.setGroup(group);
        member.setUser(user);
        member.setJoinedAt(Instant.parse("2026-03-16T10:00:00Z"));
        return member;
    }

    private Transaction buildTransaction(
            UUID transactionId,
            Group group,
            User paidBy,
            String description,
            String amount,
            String createdAt,
            String updatedAt,
            String deletedAt) {
        Transaction transaction = new Transaction();
        transaction.setId(transactionId);
        transaction.setGroup(group);
        transaction.setPaidBy(paidBy);
        transaction.setDescription(description);
        transaction.setAmount(new BigDecimal(amount));
        transaction.setCreatedAt(Instant.parse(createdAt));
        transaction.setUpdatedAt(Instant.parse(updatedAt));
        transaction.setDeletedAt(deletedAt == null ? null : Instant.parse(deletedAt));
        return transaction;
    }

    private TransactionSplit buildSplit(Transaction transaction, User user, String amount) {
        TransactionSplit split = new TransactionSplit();
        split.setTransaction(transaction);
        split.setUser(user);
        split.setAmount(new BigDecimal(amount));
        return split;
    }

    private TransactionRequestDTO buildRequest(
            UUID paidByUserId,
            String amount,
            TransactionRequestDTO.SplitItem... splits) {
        TransactionRequestDTO request = new TransactionRequestDTO();
        request.setDescription("Descripcion");
        request.setPaidByUserId(paidByUserId);
        request.setAmount(new BigDecimal(amount));
        request.setSplits(Arrays.asList(splits));
        return request;
    }

    private TransactionRequestDTO.SplitItem splitItem(UUID userId, String amount) {
        TransactionRequestDTO.SplitItem split = new TransactionRequestDTO.SplitItem();
        split.setUserId(userId);
        split.setAmount(new BigDecimal(amount));
        return split;
    }

    private List<TransactionSplit> copySplits(Iterable<TransactionSplit> splits) {
        List<TransactionSplit> copiedSplits = new ArrayList<>();
        splits.forEach(copiedSplits::add);
        return copiedSplits;
    }
}
