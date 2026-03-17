package com.splitscan.RestAPI.Services;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyList;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import java.time.Instant;
import java.util.Arrays;
import java.util.List;
import java.util.Optional;
import java.util.UUID;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Captor;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.http.HttpStatus;
import org.springframework.web.server.ResponseStatusException;

import com.splitscan.RestAPI.DTOs.group.GroupRequestDTO;
import com.splitscan.RestAPI.DTOs.group.GroupResponseDTO;
import com.splitscan.RestAPI.Models.Group;
import com.splitscan.RestAPI.Models.GroupMember;
import com.splitscan.RestAPI.Models.User;
import com.splitscan.RestAPI.Repositories.GroupMemberRepository;
import com.splitscan.RestAPI.Repositories.GroupRepository;
import com.splitscan.RestAPI.Repositories.UserRepository;

@ExtendWith(MockitoExtension.class)
class GroupServiceTest {

    @Mock
    private GroupRepository groupRepository;

    @Mock
    private GroupMemberRepository groupMemberRepository;

    @Mock
    private UserRepository userRepository;

    @InjectMocks
    private GroupService groupService;

    @Captor
    private ArgumentCaptor<List<GroupMember>> membersCaptor;

    @Captor
    private ArgumentCaptor<GroupMember> memberCaptor;

    @Test
    void createGroupAddsCreatorAsInitialMember() {
        UUID creatorId = UUID.randomUUID();
        User creator = buildUser(creatorId, "Enrique", "enrique@example.com");
        GroupRequestDTO request = new GroupRequestDTO();
        request.setName("Viaje a Madrid");

        when(userRepository.findById(creatorId)).thenReturn(Optional.of(creator));
        when(groupRepository.save(any(Group.class))).thenAnswer(invocation -> invocation.getArgument(0));
        when(groupMemberRepository.findByGroup_Id(any(UUID.class)))
                .thenAnswer(invocation -> List.of(buildMember(buildGroup(invocation.getArgument(0), request.getName()), creator)));

        GroupResponseDTO response = groupService.createGroup(creatorId, request);

        verify(groupMemberRepository).save(memberCaptor.capture());
        GroupMember savedMember = memberCaptor.getValue();
        assertEquals(creatorId, savedMember.getUser().getId());
        assertEquals(response.getId(), savedMember.getGroup().getId());
        assertNotNull(savedMember.getJoinedAt());
        assertEquals(1, response.getUsers().size());
        assertEquals(creatorId, response.getUsers().get(0).getId());
    }

    @Test
    void addMembersCreatesAllMembershipsAndReturnsUpdatedGroup() {
        UUID currentUserId = UUID.randomUUID();
        UUID groupId = UUID.randomUUID();
        UUID userIdOne = UUID.randomUUID();
        UUID userIdTwo = UUID.randomUUID();
        Group group = buildGroup(groupId, "Viaje a Madrid");
        User currentUser = buildUser(currentUserId, "Enrique", "enrique@example.com");
        User userOne = buildUser(userIdOne, "Laura", "laura@example.com");
        User userTwo = buildUser(userIdTwo, "Marta", "marta@example.com");

        when(groupRepository.findById(groupId)).thenReturn(Optional.of(group));
        when(groupMemberRepository.existsByGroup_IdAndUser_Id(groupId, currentUserId)).thenReturn(true);
        when(userRepository.findAllById(List.of(userIdOne, userIdTwo))).thenReturn(List.of(userOne, userTwo));
        when(groupMemberRepository.existsByGroup_IdAndUser_Id(groupId, userIdOne)).thenReturn(false);
        when(groupMemberRepository.existsByGroup_IdAndUser_Id(groupId, userIdTwo)).thenReturn(false);
        when(groupMemberRepository.findByGroup_Id(groupId))
                .thenReturn(List.of(
                        buildMember(group, currentUser),
                        buildMember(group, userOne),
                        buildMember(group, userTwo)));

        GroupResponseDTO response = groupService.addMembers(currentUserId, groupId, List.of(userIdOne, userIdTwo));

        assertEquals(groupId, response.getId());
        assertEquals(3, response.getUsers().size());
        assertTrue(response.getUsers().stream().anyMatch(user -> user.getEmail().equals("laura@example.com")));
        assertTrue(response.getUsers().stream().anyMatch(user -> user.getEmail().equals("marta@example.com")));

        verify(groupMemberRepository).saveAll(membersCaptor.capture());
        List<GroupMember> savedMembers = membersCaptor.getValue();
        assertEquals(2, savedMembers.size());
        assertEquals(groupId, savedMembers.get(0).getGroup().getId());
        assertNotNull(savedMembers.get(0).getJoinedAt());
        assertNotNull(savedMembers.get(1).getJoinedAt());
    }

    @Test
    void addMembersFailsWhenCurrentUserIsNotGroupMember() {
        UUID currentUserId = UUID.randomUUID();
        UUID groupId = UUID.randomUUID();
        Group group = buildGroup(groupId, "Viaje a Madrid");

        when(groupRepository.findById(groupId)).thenReturn(Optional.of(group));
        when(groupMemberRepository.existsByGroup_IdAndUser_Id(groupId, currentUserId)).thenReturn(false);

        ResponseStatusException ex = assertThrows(ResponseStatusException.class,
                () -> groupService.addMembers(currentUserId, groupId, List.of(UUID.randomUUID())));

        assertEquals(HttpStatus.FORBIDDEN, ex.getStatusCode());
        verify(userRepository, never()).findAllById(anyList());
        verify(groupMemberRepository, never()).saveAll(anyList());
    }

    @Test
    void addMembersFailsWhenGroupDoesNotExist() {
        UUID currentUserId = UUID.randomUUID();
        UUID groupId = UUID.randomUUID();

        when(groupRepository.findById(groupId)).thenReturn(Optional.empty());

        ResponseStatusException ex = assertThrows(ResponseStatusException.class,
                () -> groupService.addMembers(currentUserId, groupId, List.of(UUID.randomUUID())));

        assertEquals(HttpStatus.NOT_FOUND, ex.getStatusCode());
        verify(userRepository, never()).findAllById(anyList());
        verify(groupMemberRepository, never()).saveAll(anyList());
    }

    @Test
    void addMembersFailsWhenAnyUserDoesNotExist() {
        UUID currentUserId = UUID.randomUUID();
        UUID groupId = UUID.randomUUID();
        UUID userIdOne = UUID.randomUUID();
        UUID userIdTwo = UUID.randomUUID();
        Group group = buildGroup(groupId, "Viaje a Madrid");
        User userOne = buildUser(userIdOne, "Laura", "laura@example.com");

        when(groupRepository.findById(groupId)).thenReturn(Optional.of(group));
        when(groupMemberRepository.existsByGroup_IdAndUser_Id(groupId, currentUserId)).thenReturn(true);
        when(userRepository.findAllById(List.of(userIdOne, userIdTwo))).thenReturn(List.of(userOne));

        ResponseStatusException ex = assertThrows(ResponseStatusException.class,
                () -> groupService.addMembers(currentUserId, groupId, List.of(userIdOne, userIdTwo)));

        assertEquals(HttpStatus.NOT_FOUND, ex.getStatusCode());
        verify(groupMemberRepository, never()).saveAll(anyList());
    }

    @Test
    void addMembersFailsWhenAnyUserAlreadyBelongsToGroup() {
        UUID currentUserId = UUID.randomUUID();
        UUID groupId = UUID.randomUUID();
        UUID userIdOne = UUID.randomUUID();
        UUID userIdTwo = UUID.randomUUID();
        Group group = buildGroup(groupId, "Viaje a Madrid");
        User userOne = buildUser(userIdOne, "Laura", "laura@example.com");
        User userTwo = buildUser(userIdTwo, "Marta", "marta@example.com");

        when(groupRepository.findById(groupId)).thenReturn(Optional.of(group));
        when(groupMemberRepository.existsByGroup_IdAndUser_Id(groupId, currentUserId)).thenReturn(true);
        when(userRepository.findAllById(List.of(userIdOne, userIdTwo))).thenReturn(List.of(userOne, userTwo));
        when(groupMemberRepository.existsByGroup_IdAndUser_Id(groupId, userIdOne)).thenReturn(false);
        when(groupMemberRepository.existsByGroup_IdAndUser_Id(groupId, userIdTwo)).thenReturn(true);

        ResponseStatusException ex = assertThrows(ResponseStatusException.class,
                () -> groupService.addMembers(currentUserId, groupId, List.of(userIdOne, userIdTwo)));

        assertEquals(HttpStatus.CONFLICT, ex.getStatusCode());
        verify(groupMemberRepository, never()).saveAll(anyList());
    }

    @Test
    void addMembersFailsWhenRequestContainsDuplicateUserIds() {
        UUID currentUserId = UUID.randomUUID();
        UUID groupId = UUID.randomUUID();
        UUID userId = UUID.randomUUID();

        ResponseStatusException ex = assertThrows(ResponseStatusException.class,
                () -> groupService.addMembers(currentUserId, groupId, List.of(userId, userId)));

        assertEquals(HttpStatus.CONFLICT, ex.getStatusCode());
        verify(groupRepository, never()).findById(eq(groupId));
        verify(groupMemberRepository, never()).saveAll(anyList());
    }

    @Test
    void addMembersFailsWhenRequestContainsNullIds() {
        UUID currentUserId = UUID.randomUUID();
        UUID groupId = UUID.randomUUID();

        ResponseStatusException ex = assertThrows(ResponseStatusException.class,
                () -> groupService.addMembers(currentUserId, groupId, Arrays.asList(UUID.randomUUID(), null)));

        assertEquals(HttpStatus.BAD_REQUEST, ex.getStatusCode());
        verify(groupRepository, never()).findById(eq(groupId));
        verify(groupMemberRepository, never()).saveAll(anyList());
    }

    @Test
    void addMembersFailsWhenRequestContainsNoIds() {
        UUID currentUserId = UUID.randomUUID();
        UUID groupId = UUID.randomUUID();

        ResponseStatusException ex = assertThrows(ResponseStatusException.class,
                () -> groupService.addMembers(currentUserId, groupId, List.of()));

        assertEquals(HttpStatus.BAD_REQUEST, ex.getStatusCode());
        verify(groupRepository, never()).findById(eq(groupId));
        verify(groupMemberRepository, never()).saveAll(anyList());
    }

    private Group buildGroup(UUID groupId, String name) {
        Group group = new Group();
        group.setId(groupId);
        group.setName(name);
        group.setCreatedAt(Instant.parse("2026-03-16T10:00:00Z"));
        return group;
    }

    private User buildUser(UUID userId, String name, String email) {
        User user = new User();
        user.setId(userId);
        user.setName(name);
        user.setEmail(email);
        return user;
    }

    private GroupMember buildMember(Group group, User user) {
        GroupMember member = new GroupMember();
        member.setGroup(group);
        member.setUser(user);
        member.setJoinedAt(Instant.parse("2026-03-16T10:00:00Z"));
        return member;
    }
}
