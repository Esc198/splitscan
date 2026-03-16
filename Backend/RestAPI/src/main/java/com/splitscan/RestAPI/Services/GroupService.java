package com.splitscan.RestAPI.Services;

import java.time.Instant;
import java.util.List;
import java.util.UUID;

import org.springframework.stereotype.Service;

import com.splitscan.RestAPI.DTOs.group.GroupRequestDTO;
import com.splitscan.RestAPI.DTOs.group.GroupResponseDTO;
import com.splitscan.RestAPI.DTOs.user.UserResponseDTO;
import com.splitscan.RestAPI.Models.Group;
import com.splitscan.RestAPI.Models.GroupMember;
import com.splitscan.RestAPI.Models.User;
import com.splitscan.RestAPI.Repositories.GroupMemberRepository;
import com.splitscan.RestAPI.Repositories.GroupRepository;

@Service
public class GroupService {

    private final GroupRepository groupRepository;
    private final GroupMemberRepository groupMemberRepository;

    public GroupService(GroupRepository groupRepository, GroupMemberRepository groupMemberRepository) {
        this.groupRepository = groupRepository;
        this.groupMemberRepository = groupMemberRepository;
    }

    public List<GroupResponseDTO> getGroupsForUser(UUID userId) {
        return groupMemberRepository.findByUser_Id(userId).stream()
                .map(GroupMember::getGroup)
                .map(this::toResponseDTO)
                .toList();
    }

    public GroupResponseDTO getGroup(UUID groupId) {
        return groupRepository.findById(groupId)
                .map(this::toResponseDTO)
                .orElseThrow(() -> new RuntimeException("Group not found"));
    }

    public GroupResponseDTO createGroup(GroupRequestDTO dto) {
        Group group = new Group();
        group.setId(UUID.randomUUID());
        group.setName(dto.getName());
        group.setCreatedAt(Instant.now());

        Group savedGroup = groupRepository.save(group);
        return toResponseDTO(savedGroup);
    }

    private GroupResponseDTO toResponseDTO(Group group) {
        List<UserResponseDTO> users = groupMemberRepository.findByGroup_Id(group.getId()).stream()
                .map(GroupMember::getUser)
                .map(this::toUserResponseDTO)
                .toList();

        return new GroupResponseDTO(group.getId(), group.getName(), group.getCreatedAt(), users);
    }

    private UserResponseDTO toUserResponseDTO(User user) {
        return new UserResponseDTO(user.getId(), user.getName(), user.getEmail());
    }

}