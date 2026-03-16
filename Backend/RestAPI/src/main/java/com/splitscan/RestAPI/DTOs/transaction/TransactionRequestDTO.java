package com.splitscan.RestAPI.DTOs.transaction;

import java.math.BigDecimal;
import java.util.List;
import java.util.UUID;

import lombok.Getter;
import lombok.Setter;

@Getter
@Setter
public class TransactionRequestDTO {

    private String description;
    private UUID paidByUserId;
    private BigDecimal amount;
    private List<SplitItem> splits;

    @Getter
    @Setter
    public static class SplitItem {
        private UUID userId;
        private BigDecimal amount;
    }
}
