package com.splitscan.RestAPI.DTOs.group;

import java.time.Instant;
import java.util.List;
import java.util.UUID;

import com.splitscan.RestAPI.DTOs.user.UserResponseDTO;

import lombok.AllArgsConstructor;
import lombok.Getter;

@Getter
@AllArgsConstructor
public class GroupResponseDTO {
    private UUID id;
    private String name;
    private Instant createdAt;
    private List<UserResponseDTO> users;
}
