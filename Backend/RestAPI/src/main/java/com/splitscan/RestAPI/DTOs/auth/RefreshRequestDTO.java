package com.splitscan.RestAPI.DTOs.auth;

import lombok.Getter;
import lombok.Setter;

@Getter
@Setter
public class RefreshRequestDTO {

    private String refreshToken;
}
