package com.splitscan.RestAPI.Services;

import java.util.List;
import java.util.UUID;
import java.util.stream.Collectors;

import org.springframework.stereotype.Service;

import com.splitscan.RestAPI.Models.Group;
import com.splitscan.RestAPI.Models.GroupMember;
import com.splitscan.RestAPI.Repositories.GroupMemberRepository;
import com.splitscan.RestAPI.Repositories.GroupRepository;

@Service
public class GroupService {

    private final GroupRepository groupRepository;
    private final GroupMemberRepository groupMemberRepository;

    public GroupService(GroupRepository groupRepository,
                        GroupMemberRepository groupMemberRepository) {
        this.groupRepository = groupRepository;
        this.groupMemberRepository = groupMemberRepository;
    }

    public List<Group> getGroupsForUser(UUID userId) {
        List<GroupMember> memberships = groupMemberRepository.findByUserId(userId);

        return memberships
                .stream()
                .map(GroupMember::getGroup)
                .collect(Collectors.toList());
    }

    public Group getGroup(UUID groupId) {
        return groupRepository.findById(groupId)
                .orElseThrow(() -> new RuntimeException("Group not found"));
    }

    public Group createGroup(Group group) {
        return groupRepository.save(group);
    }

    public boolean userInGroup(UUID groupId, UUID userId) {
        return groupMemberRepository.existsByGroupIdAndUserId(groupId, userId);
    }

	public List<Group> getAllGroups() {
		return groupRepository.findAll();
	}
}