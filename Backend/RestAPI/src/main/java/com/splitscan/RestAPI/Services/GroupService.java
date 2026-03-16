package com.splitscan.RestAPI.Services;

import org.springframework.stereotype.Service;

import com.splitscan.RestAPI.Models.Group;
import com.splitscan.RestAPI.Repositories.GroupRepository;

import java.util.List;
import java.util.UUID;

@Service
public class GroupService {

    private final GroupRepository groupRepository;

    public GroupService(GroupRepository groupRepository) {
        this.groupRepository = groupRepository;
    }

    public List<Group> getAllGroups() {
        return groupRepository.findAll();
    }

    public Group getGroupById(UUID id) {
        return groupRepository.findById(id).orElse(null);
    }

    public Group createGroup(Group group) {
        return groupRepository.save(group);
    }

    public void deleteGroup(UUID id) {
        groupRepository.deleteById(id);
    }
}