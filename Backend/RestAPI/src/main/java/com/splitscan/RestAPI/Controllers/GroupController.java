package com.splitscan.RestAPI.Controllers;

import com.splitscan.RestAPI.DTOs.group.GroupMembersRequestDTO;
import com.splitscan.RestAPI.DTOs.group.GroupRequestDTO;
import com.splitscan.RestAPI.DTOs.group.GroupResponseDTO;
import com.splitscan.RestAPI.Security.CurrentUserService;
import com.splitscan.RestAPI.Services.GroupService;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.UUID;


@RestController
@RequestMapping("/groups")
public class GroupController {

    private final GroupService groupService;
    private final CurrentUserService currentUserService;

    public GroupController(GroupService groupService, CurrentUserService currentUserService) {
        this.groupService = groupService;
        this.currentUserService = currentUserService;
    }

    @GetMapping("/mine")
    public List<GroupResponseDTO> getMyGroups() {
        return groupService.getMyGroups(currentUserService.requireCurrentUserId());
    }

    @PostMapping
    public GroupResponseDTO createGroup(@RequestBody GroupRequestDTO dto) {
        return groupService.createGroup(currentUserService.requireCurrentUserId(), dto);
    }

    @GetMapping("/{groupId}")
    public GroupResponseDTO getGroup(@PathVariable UUID groupId) {
        return groupService.getGroup(currentUserService.requireCurrentUserId(), groupId);
    }
    

    @PostMapping("/{groupId}/members")
    public GroupResponseDTO addMembers(@PathVariable UUID groupId, @RequestBody GroupMembersRequestDTO dto) {
        return groupService.addMembers(currentUserService.requireCurrentUserId(), groupId, dto.getUserIds());
    }

}
