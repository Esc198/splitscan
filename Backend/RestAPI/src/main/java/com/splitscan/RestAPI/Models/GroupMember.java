package com.splitscan.RestAPI.Models;

import java.time.Instant;

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
@IdClass(GroupMemberId.class)
@Table(name = "group_members")
@Getter
@Setter
public class GroupMember {

    @Id
    @ManyToOne
    @JoinColumn(name = "group_id")
    @Getter
    @Setter
    private Group group;

    @Id
    @ManyToOne
    @JoinColumn(name = "user_id")
    @Getter
    @Setter
    private User user;

    @Getter
    @Setter
    @Column(nullable = false)
    private Instant joinedAt;

    public GroupMember() {}




}