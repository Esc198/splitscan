package com.splitscan.RestAPI.DTOs.user;

import lombok.Getter;
import lombok.Setter;

@Getter
@Setter
public class UpdateMeRequestDTO {

    private String name;
    private String email;
    private String currentPassword;
    private String newPassword;
}
