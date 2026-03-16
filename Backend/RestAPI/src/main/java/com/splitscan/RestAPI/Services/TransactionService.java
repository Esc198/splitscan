package com.splitscan.RestAPI.Services;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.function.Function;
import java.util.stream.Collectors;

import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
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

@Service
public class TransactionService {

    private static final int MONEY_SCALE = 2;

    private final GroupRepository groupRepository;
    private final GroupMemberRepository groupMemberRepository;
    private final TransactionRepository transactionRepository;
    private final TransactionSplitRepository transactionSplitRepository;

    public TransactionService(
            GroupRepository groupRepository,
            GroupMemberRepository groupMemberRepository,
            TransactionRepository transactionRepository,
            TransactionSplitRepository transactionSplitRepository) {
        this.groupRepository = groupRepository;
        this.groupMemberRepository = groupMemberRepository;
        this.transactionRepository = transactionRepository;
        this.transactionSplitRepository = transactionSplitRepository;
    }

    @Transactional(readOnly = true)
    public List<TransactionResponseDTO> getTransactions(UUID groupId, Instant since) {
        getGroupEntityById(groupId);

        List<Transaction> transactions = since == null
                ? transactionRepository.findByGroup_IdAndDeletedAtIsNullOrderByUpdatedAtAsc(groupId)
                : transactionRepository.findByGroup_IdAndUpdatedAtGreaterThanEqualOrderByUpdatedAtAsc(groupId, since);

        return toResponseDTOs(transactions);
    }

    @Transactional(readOnly = true)
    public TransactionResponseDTO getTransaction(UUID groupId, UUID transactionId) {
        getGroupEntityById(groupId);
        Transaction transaction = getActiveTransactionEntity(groupId, transactionId);
        List<TransactionSplit> splits = getSplitsByTransactionIds(List.of(transaction.getId()))
                .getOrDefault(transaction.getId(), List.of());
        return toResponseDTO(transaction, splits);
    }

    @Transactional
    public TransactionResponseDTO createTransaction(UUID groupId, TransactionRequestDTO dto) {
        Group group = getGroupEntityById(groupId);
        ValidatedTransactionInput validatedInput = validateTransactionRequest(groupId, dto);
        Instant now = Instant.now();

        Transaction transaction = new Transaction();
        transaction.setId(UUID.randomUUID());
        transaction.setGroup(group);
        transaction.setPaidBy(validatedInput.paidBy());
        transaction.setDescription(dto.getDescription());
        transaction.setAmount(dto.getAmount());
        transaction.setCreatedAt(now);
        transaction.setUpdatedAt(now);
        transaction.setDeletedAt(null);

        Transaction savedTransaction = transactionRepository.save(transaction);
        List<TransactionSplit> savedSplits = transactionSplitRepository.saveAll(
                buildSplits(savedTransaction, dto.getSplits(), validatedInput.groupUsersById()));

        return toResponseDTO(savedTransaction, savedSplits);
    }

    @Transactional
    public TransactionResponseDTO updateTransaction(UUID groupId, UUID transactionId, TransactionRequestDTO dto) {
        getGroupEntityById(groupId);
        Transaction transaction = getActiveTransactionEntity(groupId, transactionId);
        ValidatedTransactionInput validatedInput = validateTransactionRequest(groupId, dto);
        Instant now = Instant.now();

        transaction.setDescription(dto.getDescription());
        transaction.setPaidBy(validatedInput.paidBy());
        transaction.setAmount(dto.getAmount());
        transaction.setUpdatedAt(now);

        Transaction savedTransaction = transactionRepository.save(transaction);
        transactionSplitRepository.deleteByTransaction_Id(savedTransaction.getId());
        List<TransactionSplit> savedSplits = transactionSplitRepository.saveAll(
                buildSplits(savedTransaction, dto.getSplits(), validatedInput.groupUsersById()));

        return toResponseDTO(savedTransaction, savedSplits);
    }

    @Transactional
    public void deleteTransaction(UUID groupId, UUID transactionId) {
        getGroupEntityById(groupId);
        Transaction transaction = getActiveTransactionEntity(groupId, transactionId);
        Instant now = Instant.now();

        transaction.setDeletedAt(now);
        transaction.setUpdatedAt(now);

        transactionRepository.save(transaction);
    }

    private Group getGroupEntityById(UUID groupId) {
        return groupRepository.findById(groupId)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Group not found: " + groupId));
    }

    private Transaction getActiveTransactionEntity(UUID groupId, UUID transactionId) {
        return transactionRepository.findByIdAndGroup_IdAndDeletedAtIsNull(transactionId, groupId)
                .orElseThrow(() -> new ResponseStatusException(
                        HttpStatus.NOT_FOUND,
                        "Transaction not found: " + transactionId));
    }

    private ValidatedTransactionInput validateTransactionRequest(UUID groupId, TransactionRequestDTO dto) {
        if (dto == null) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Transaction body is required");
        }

        validateAmount(dto.getAmount(), "amount");

        if (dto.getPaidByUserId() == null) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "paidByUserId is required");
        }

        List<TransactionRequestDTO.SplitItem> splits = dto.getSplits();
        if (splits == null || splits.isEmpty()) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "splits must contain at least one item");
        }

        Map<UUID, User> groupUsersById = getGroupUsersById(groupId);
        User paidBy = groupUsersById.get(dto.getPaidByUserId());
        if (paidBy == null) {
            throw new ResponseStatusException(
                    HttpStatus.CONFLICT,
                    "paidBy user does not belong to group: " + dto.getPaidByUserId());
        }

        LinkedHashSet<UUID> uniqueSplitUsers = new LinkedHashSet<>();
        BigDecimal splitTotal = BigDecimal.ZERO;
        for (TransactionRequestDTO.SplitItem split : splits) {
            if (split == null) {
                throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "splits cannot contain null items");
            }
            if (split.getUserId() == null) {
                throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "split userId is required");
            }
            if (!uniqueSplitUsers.add(split.getUserId())) {
                throw new ResponseStatusException(
                        HttpStatus.CONFLICT,
                        "splits cannot contain duplicate userIds: " + split.getUserId());
            }
            if (!groupUsersById.containsKey(split.getUserId())) {
                throw new ResponseStatusException(
                        HttpStatus.CONFLICT,
                        "split user does not belong to group: " + split.getUserId());
            }

            validateAmount(split.getAmount(), "split amount");
            splitTotal = splitTotal.add(split.getAmount());
        }

        if (splitTotal.compareTo(dto.getAmount()) != 0) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "sum of splits must equal transaction amount");
        }

        return new ValidatedTransactionInput(paidBy, groupUsersById);
    }

    private void validateAmount(BigDecimal amount, String fieldName) {
        if (amount == null) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, fieldName + " is required");
        }
        if (amount.compareTo(BigDecimal.ZERO) <= 0) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, fieldName + " must be greater than zero");
        }
        if (amount.scale() > MONEY_SCALE) {
            throw new ResponseStatusException(
                    HttpStatus.BAD_REQUEST,
                    fieldName + " must have at most " + MONEY_SCALE + " decimal places");
        }
    }

    private Map<UUID, User> getGroupUsersById(UUID groupId) {
        return groupMemberRepository.findByGroup_Id(groupId).stream()
                .map(GroupMember::getUser)
                .collect(Collectors.toMap(User::getId, Function.identity(), (left, right) -> left));
    }

    private List<TransactionSplit> buildSplits(
            Transaction transaction,
            List<TransactionRequestDTO.SplitItem> splitItems,
            Map<UUID, User> groupUsersById) {
        return splitItems.stream()
                .map(splitItem -> buildSplit(transaction, splitItem, groupUsersById))
                .toList();
    }

    private TransactionSplit buildSplit(
            Transaction transaction,
            TransactionRequestDTO.SplitItem splitItem,
            Map<UUID, User> groupUsersById) {
        TransactionSplit split = new TransactionSplit();
        split.setTransaction(transaction);
        split.setUser(groupUsersById.get(splitItem.getUserId()));
        split.setAmount(splitItem.getAmount());
        return split;
    }

    private Map<UUID, List<TransactionSplit>> getSplitsByTransactionIds(List<UUID> transactionIds) {
        if (transactionIds.isEmpty()) {
            return Map.of();
        }

        return transactionSplitRepository.findByTransaction_IdInOrderByTransaction_IdAscUser_IdAsc(transactionIds)
                .stream()
                .collect(Collectors.groupingBy(split -> split.getTransaction().getId()));
    }

    private List<TransactionResponseDTO> toResponseDTOs(List<Transaction> transactions) {
        Map<UUID, List<TransactionSplit>> splitsByTransactionId = getSplitsByTransactionIds(
                transactions.stream()
                        .map(Transaction::getId)
                        .toList());

        return transactions.stream()
                .map(transaction -> toResponseDTO(
                        transaction,
                        splitsByTransactionId.getOrDefault(transaction.getId(), List.of())))
                .toList();
    }

    private TransactionResponseDTO toResponseDTO(Transaction transaction, List<TransactionSplit> splits) {
        List<TransactionResponseDTO.SplitItem> splitItems = splits.stream()
                .sorted((left, right) -> left.getUser().getId().compareTo(right.getUser().getId()))
                .map(split -> new TransactionResponseDTO.SplitItem(split.getUser().getId(), split.getAmount()))
                .toList();

        return new TransactionResponseDTO(
                transaction.getId(),
                transaction.getDescription(),
                transaction.getPaidBy().getId(),
                transaction.getAmount(),
                transaction.getCreatedAt(),
                transaction.getUpdatedAt(),
                transaction.getDeletedAt(),
                splitItems);
    }

    private record ValidatedTransactionInput(User paidBy, Map<UUID, User> groupUsersById) {
    }
}
