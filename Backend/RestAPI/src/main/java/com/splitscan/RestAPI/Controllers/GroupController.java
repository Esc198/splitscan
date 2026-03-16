package com.splitscan.RestAPI.Controllers;

import org.springframework.web.bind.annotation.RestController;

import com.splitscan.RestAPI.Models.Group;
import com.splitscan.RestAPI.Services.GroupService;

import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/groups")
public class GroupController {

    private final GroupService groupService;

    public GroupController(GroupService groupService) {
        this.groupService = groupService;
    }

    @GetMapping
    public List<Group> getGroups() {
        return groupService.getAllGroups();
    }
}