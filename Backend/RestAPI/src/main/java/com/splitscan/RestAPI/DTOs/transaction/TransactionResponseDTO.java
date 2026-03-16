package com.splitscan.RestAPI.DTOs.transaction;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.List;
import java.util.UUID;

import lombok.AllArgsConstructor;
import lombok.Getter;

@Getter
@AllArgsConstructor
public class TransactionResponseDTO {

    private UUID id;
    private String description;
    private UUID paidByUserId;
    private BigDecimal amount;
    private Instant createdAt;
    private Instant updatedAt;
    private Instant deletedAt;
    private List<SplitItem> splits;

    @Getter
    @AllArgsConstructor
    public static class SplitItem {
        private UUID userId;
        private BigDecimal amount;
    }
}
