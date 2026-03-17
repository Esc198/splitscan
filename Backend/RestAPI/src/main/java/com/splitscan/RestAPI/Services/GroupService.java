package com.splitscan.RestAPI.Services;

import java.time.Instant;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.function.Function;
import java.util.stream.Collectors;

import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.http.HttpStatus;
import org.springframework.web.server.ResponseStatusException;

import com.splitscan.RestAPI.DTOs.group.GroupRequestDTO;
import com.splitscan.RestAPI.DTOs.group.GroupResponseDTO;
import com.splitscan.RestAPI.DTOs.user.UserResponseDTO;
import com.splitscan.RestAPI.Models.Group;
import com.splitscan.RestAPI.Models.GroupMember;
import com.splitscan.RestAPI.Models.User;
import com.splitscan.RestAPI.Repositories.GroupMemberRepository;
import com.splitscan.RestAPI.Repositories.GroupRepository;
import com.splitscan.RestAPI.Repositories.UserRepository;

@Service
public class GroupService {

    private final GroupRepository groupRepository;
    private final GroupMemberRepository groupMemberRepository;
    private final UserRepository userRepository;

    public GroupService(GroupRepository groupRepository, GroupMemberRepository groupMemberRepository,
            UserRepository userRepository) {
        this.groupRepository = groupRepository;
        this.groupMemberRepository = groupMemberRepository;
        this.userRepository = userRepository;
    }

    public List<GroupResponseDTO> getMyGroups(UUID currentUserId) {
        return groupMemberRepository.findByUser_Id(currentUserId).stream()
                .map(GroupMember::getGroup)
                .map(this::toResponseDTO)
                .toList();
    }

    public GroupResponseDTO getGroup(UUID currentUserId, UUID groupId) {
        Group group = getGroupEntityById(groupId);
        validateGroupMembership(currentUserId, groupId);
        return toResponseDTO(group);
    }

    @Transactional
    public GroupResponseDTO createGroup(UUID currentUserId, GroupRequestDTO dto) {
        Group group = new Group();
        group.setId(UUID.randomUUID());
        group.setName(dto.getName());
        group.setCreatedAt(Instant.now());

        Group savedGroup = groupRepository.save(group);
        User creator = getUserEntityById(currentUserId);
        groupMemberRepository.save(buildGroupMember(savedGroup, creator, Instant.now()));
        return toResponseDTO(savedGroup);
    }

    @Transactional
    public GroupResponseDTO addMembers(UUID currentUserId, UUID groupId, List<UUID> userIds) {
        validateUserIds(userIds);

        Group group = getGroupEntityById(groupId);
        validateGroupMembership(currentUserId, groupId);
        List<User> users = getUsersByIds(userIds);

        for (UUID userId : userIds) {
            if (groupMemberRepository.existsByGroup_IdAndUser_Id(groupId, userId)) {
                throw new ResponseStatusException(HttpStatus.CONFLICT,
                        "User already belongs to group: " + userId);
            }
        }

        Instant joinedAt = Instant.now();
        List<GroupMember> members = users.stream()
                .map(user -> buildGroupMember(group, user, joinedAt))
                .toList();

        groupMemberRepository.saveAll(members);
        return toResponseDTO(group);
    }

    private void validateUserIds(List<UUID> userIds) {
        if (userIds == null || userIds.isEmpty()) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "userIds must contain at least one user id");
        }
        if (userIds.stream().anyMatch(userId -> userId == null)) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "userIds cannot contain null values");
        }

        LinkedHashSet<UUID> uniqueUserIds = new LinkedHashSet<>(userIds);
        if (uniqueUserIds.size() != userIds.size()) {
            throw new ResponseStatusException(HttpStatus.CONFLICT, "userIds cannot contain duplicates");
        }
    }

    private Group getGroupEntityById(UUID groupId) {
        return groupRepository.findById(groupId)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Group not found: " + groupId));
    }

    private User getUserEntityById(UUID userId) {
        return userRepository.findById(userId)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "User not found: " + userId));
    }

    private List<User> getUsersByIds(List<UUID> userIds) {
        List<User> users = userRepository.findAllById(userIds);
        Map<UUID, User> usersById = users.stream()
                .collect(Collectors.toMap(User::getId, Function.identity()));

        List<UUID> missingUserIds = userIds.stream()
                .filter(userId -> !usersById.containsKey(userId))
                .toList();

        if (!missingUserIds.isEmpty()) {
            throw new ResponseStatusException(HttpStatus.NOT_FOUND, "Users not found: " + missingUserIds);
        }

        return userIds.stream()
                .map(usersById::get)
                .toList();
    }

    private GroupMember buildGroupMember(Group group, User user, Instant joinedAt) {
        GroupMember member = new GroupMember();
        member.setGroup(group);
        member.setUser(user);
        member.setJoinedAt(joinedAt);
        return member;
    }

    private void validateGroupMembership(UUID currentUserId, UUID groupId) {
        if (!groupMemberRepository.existsByGroup_IdAndUser_Id(groupId, currentUserId)) {
            throw new ResponseStatusException(
                    HttpStatus.FORBIDDEN,
                    "User is not a member of group: " + groupId);
        }
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
