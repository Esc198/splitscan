package com.splitscan.RestAPI.Models;

import java.util.UUID;

import jakarta.persistence.Entity;
import jakarta.persistence.Table;
import lombok.AllArgsConstructor;
import lombok.NoArgsConstructor;


@Entity
@Table(name = "users")
@AllArgsConstructor
@NoArgsConstructor
public class User {

    private UUID id;
    private String name;


    public UUID getId() { return id; }
    public String getName() { return name; }
}