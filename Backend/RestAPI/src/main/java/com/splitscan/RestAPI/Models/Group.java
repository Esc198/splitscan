package com.splitscan.RestAPI.Models;

import java.time.Instant;
import java.util.UUID;

import jakarta.persistence.*;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

@Entity
@Table(name = "groups")
@NoArgsConstructor
public class Group {

    @Id
    @Getter
    @Setter
    private UUID id;

    @Getter
    @Setter
    private String name;
    
    @Column(nullable = false)
    @Getter
    @Setter
    private Instant createdAt;
    
    public Group(String name) {
        this.name = name;
    }

}