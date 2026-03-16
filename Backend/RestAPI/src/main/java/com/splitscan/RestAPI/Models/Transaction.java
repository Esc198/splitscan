package com.splitscan.RestAPI.Models;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.UUID;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.Table;
import lombok.Getter;
import lombok.Setter;

@Entity
@Table(name = "transactions")
public class Transaction {

    @Id
    @Getter
    @Setter
    private UUID id;

    @ManyToOne
    @JoinColumn(name = "group_id", nullable = false)
    @Getter
    @Setter
    private Group group;

    @ManyToOne
    @JoinColumn(name = "paid_by", nullable = false)
    @Getter
    @Setter
    private User paidBy;

    @Getter
    @Setter
    private String description;

    @Column(nullable = false)
    @Getter
    @Setter
    private BigDecimal amount;

    @Column(nullable = false)
    @Getter
    @Setter
    private Instant createdAt;

    @Column(nullable = false)
    @Getter
    @Setter
    private Instant updatedAt;

    @Getter
    @Setter
    private Instant deletedAt;



   
}