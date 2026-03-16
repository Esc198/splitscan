package com.splitscan.RestAPI.Repositories;

import java.util.List;
import java.util.UUID;

import org.springframework.data.jpa.repository.JpaRepository;

import com.splitscan.RestAPI.Models.GroupMember;
import com.splitscan.RestAPI.Models.GroupMemberId;

public interface GroupMemberRepository extends JpaRepository<GroupMember, GroupMemberId> {

    boolean existsByGroupIdAndUserId(UUID groupId, UUID userId);

    List<GroupMember> findByUserId(UUID userId);

    List<GroupMember> findByGroupId(UUID groupId);
}