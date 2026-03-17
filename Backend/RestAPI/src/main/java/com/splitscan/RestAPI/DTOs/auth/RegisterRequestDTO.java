package com.splitscan.RestAPI.DTOs.auth;

import lombok.Getter;
import lombok.Setter;

@Getter
@Setter
public class RegisterRequestDTO {

    private String name;
    private String email;
    private String password;
}
