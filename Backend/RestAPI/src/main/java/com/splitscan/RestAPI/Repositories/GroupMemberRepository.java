package com.splitscan.RestAPI.Repositories;

import java.util.List;
import java.util.UUID;

import org.springframework.data.jpa.repository.JpaRepository;

import com.splitscan.RestAPI.Models.GroupMember;
import com.splitscan.RestAPI.Models.GroupMemberId;

public interface GroupMemberRepository extends JpaRepository<GroupMember, GroupMemberId> {

    boolean existsByGroup_IdAndUser_Id(UUID groupId, UUID userId);

    List<GroupMember> findByUser_Id(UUID userId);

    List<GroupMember> findByGroup_Id(UUID groupId);
}