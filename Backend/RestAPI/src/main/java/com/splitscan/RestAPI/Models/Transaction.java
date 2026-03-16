package com.splitscan.RestAPI.Models;

import java.math.BigDecimal;
import java.util.List;
import java.util.UUID;

import jakarta.persistence.Entity;
import jakarta.persistence.Table;
import lombok.Getter;

@Entity
@Table(name = "transactions")

public class Transaction {
	@Getter
    private UUID id;
    @Getter
    private String description;
    @Getter
    private User pagador;
    @Getter	
    private List<User> deudores;
    @Getter	
    private BigDecimal amount;


}