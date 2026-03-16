package com.splitscan.RestAPI.Repositories;

import java.time.Instant;
import java.util.List;
import java.util.UUID;

import org.springframework.data.jpa.repository.JpaRepository;

import com.splitscan.RestAPI.Models.Transaction;



public interface TransactionRepository extends JpaRepository<Transaction, UUID> {

    List<Transaction> findByGroup_IdAndDeletedAtIsNullOrderByCreatedAtDesc(UUID groupId);

    List<Transaction> findByGroup_IdAndCreatedAtBetweenAndDeletedAtIsNullOrderByCreatedAtDesc(
            UUID groupId,
            Instant from,
            Instant to
    );

    List<Transaction> findByUpdatedAtAfterOrderByUpdatedAtAsc(Instant updatedAt);
}