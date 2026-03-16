package com.splitscan.RestAPI.DTOs.group;

import java.util.List;
import java.util.UUID;

import lombok.Getter;
import lombok.Setter;

@Getter
@Setter
public class GroupMembersRequestDTO {
    private List<UUID> userIds;
}
