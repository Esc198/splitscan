package com.splitscan.RestAPI.Models;
import java.math.BigDecimal;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.IdClass;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.Table;
import lombok.Getter;
import lombok.Setter;

@Entity
@IdClass(TransactionSplitId.class)
@Table(name = "transaction_splits")
public class TransactionSplit {

    @Id
    @ManyToOne
    @JoinColumn(name = "transaction_id")
    @Getter
    @Setter
    private Transaction transaction;

    @Id
    @ManyToOne
    @JoinColumn(name = "user_id")
    @Getter
    @Setter
    private User user;

    @Column(nullable = false)
    @Getter
    @Setter
    private BigDecimal amount;

    public TransactionSplit() {}


}