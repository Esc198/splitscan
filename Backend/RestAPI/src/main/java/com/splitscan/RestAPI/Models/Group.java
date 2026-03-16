package com.splitscan.RestAPI.Models;

import java.time.Instant;
import java.util.List;
import java.util.UUID;

import jakarta.persistence.*;
import lombok.Getter;
import lombok.Setter;

@Entity
@Table(name = "groups")
public class Group {

    @Id
    @Getter
    private UUID id;
    @Getter
    @Setter
    private String name;
    
    @Column(nullable = false)
    private Instant createdAt;
    
    public Group(String name) {
        this.name = name;
    }

}