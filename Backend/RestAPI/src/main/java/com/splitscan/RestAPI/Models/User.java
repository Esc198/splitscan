package com.splitscan.RestAPI.Models;


import jakarta.persistence.*;
import lombok.Getter;
import lombok.Setter;

import java.util.UUID;

@Entity
@Table(name = "users")
public class User {

    @Id
    @Getter
    @Setter
    private UUID id;    
    
    @Getter
    @Setter
    @Column(nullable = false)
    private String name;

    @Getter
    @Setter
    @Column(unique = true)
    private String email;

    public User() {}



}