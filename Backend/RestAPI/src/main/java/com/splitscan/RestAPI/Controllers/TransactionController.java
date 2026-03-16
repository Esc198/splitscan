package com.splitscan.RestAPI.Controllers;

import java.time.Instant;
import java.util.List;
import java.util.UUID;

import org.springframework.format.annotation.DateTimeFormat;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import com.splitscan.RestAPI.DTOs.transaction.TransactionRequestDTO;
import com.splitscan.RestAPI.DTOs.transaction.TransactionResponseDTO;
import com.splitscan.RestAPI.Services.TransactionService;

@RestController
@RequestMapping("/groups/{groupId}/transactions")
public class TransactionController {

    private final TransactionService transactionService;

    public TransactionController(TransactionService transactionService) {
        this.transactionService = transactionService;
    }

    @GetMapping
    public List<TransactionResponseDTO> getTransactions(
            @PathVariable UUID groupId,
            @RequestParam(required = false) @DateTimeFormat(iso = DateTimeFormat.ISO.DATE_TIME) Instant since) {
        return transactionService.getTransactions(groupId, since);
    }

    @GetMapping("/{transactionId}")
    public TransactionResponseDTO getTransaction(@PathVariable UUID groupId, @PathVariable UUID transactionId) {
        return transactionService.getTransaction(groupId, transactionId);
    }

    @PostMapping
    public ResponseEntity<TransactionResponseDTO> createTransaction(
            @PathVariable UUID groupId,
            @RequestBody TransactionRequestDTO dto) {
        TransactionResponseDTO created = transactionService.createTransaction(groupId, dto);
        return ResponseEntity.status(HttpStatus.CREATED).body(created);
    }

    @PutMapping("/{transactionId}")
    public TransactionResponseDTO updateTransaction(
            @PathVariable UUID groupId,
            @PathVariable UUID transactionId,
            @RequestBody TransactionRequestDTO dto) {
        return transactionService.updateTransaction(groupId, transactionId, dto);
    }

    @DeleteMapping("/{transactionId}")
    public ResponseEntity<Void> deleteTransaction(@PathVariable UUID groupId, @PathVariable UUID transactionId) {
        transactionService.deleteTransaction(groupId, transactionId);
        return ResponseEntity.noContent().build();
    }
}
