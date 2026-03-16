package com.splitscan.RestAPI.Controllers;

import org.springframework.web.bind.annotation.RestController;

import com.splitscan.RestAPI.DTOs.group.GroupRequestDTO;
import com.splitscan.RestAPI.DTOs.group.GroupResponseDTO;
import com.splitscan.RestAPI.Services.GroupService;

import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.UUID;

@RestController
@RequestMapping("/groups")
public class GroupController {

    private final GroupService groupService;

    public GroupController(GroupService groupService) {
        this.groupService = groupService;
    }

    @GetMapping("{userId}")
    public List<GroupResponseDTO> getGroups(@PathVariable UUID userId) {
        return groupService.getGroupsForUser(userId);
    }

    @PostMapping
    public GroupResponseDTO createGroup(@RequestBody GroupRequestDTO dto) {
        return groupService.createGroup(dto);
    }
}