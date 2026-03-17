package com.splitscan.RestAPI.DTOs.auth;

import java.time.Instant;

import com.splitscan.RestAPI.DTOs.user.UserResponseDTO;

import lombok.AllArgsConstructor;
import lombok.Getter;

@Getter
@AllArgsConstructor
public class AuthResponseDTO {

    private String accessToken;
    private String refreshToken;
    private Instant accessTokenExpiresAt;
    private UserResponseDTO user;
}
