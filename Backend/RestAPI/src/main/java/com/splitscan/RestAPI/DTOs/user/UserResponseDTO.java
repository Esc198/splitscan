package com.splitscan.RestAPI.DTOs.user;

import java.util.UUID;

import lombok.AllArgsConstructor;
import lombok.Getter;

@Getter
@AllArgsConstructor
public class UserResponseDTO {
    private UUID id;
    private String name;
    private String email;
}