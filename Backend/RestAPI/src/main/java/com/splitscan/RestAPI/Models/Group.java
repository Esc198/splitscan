package com.splitscan.RestAPI.Models;

import java.util.List;
import java.util.UUID;

import jakarta.persistence.*;
import lombok.Getter;

@Entity
@Table(name = "groups")
public class Group {

    @Id
    @Getter
    private UUID id;
    @Getter
    private String name;
    @Getter
    private List<User> members;
    @Getter
    private List<Transaction> transactions;
    
    public Group(String name) {
        this.name = name;
    }

    public UUID getId() { return id; }

    public String getName() { return name; }

    public void setName(String name) {
        this.name = name;
    }
}