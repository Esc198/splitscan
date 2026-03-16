package com.splitscan.RestAPI.Repositories;

import java.util.Collection;
import java.util.List;
import java.util.UUID;

import org.springframework.data.jpa.repository.JpaRepository;

import com.splitscan.RestAPI.Models.TransactionSplit;
import com.splitscan.RestAPI.Models.TransactionSplitId;

public interface TransactionSplitRepository extends JpaRepository<TransactionSplit, TransactionSplitId> {

    List<TransactionSplit> findByTransaction_Id(UUID transactionId);

    List<TransactionSplit> findByUser_Id(UUID userId);

    List<TransactionSplit> findByTransaction_IdInOrderByTransaction_IdAscUser_IdAsc(Collection<UUID> transactionIds);

    void deleteByTransaction_Id(UUID transactionId);
}
