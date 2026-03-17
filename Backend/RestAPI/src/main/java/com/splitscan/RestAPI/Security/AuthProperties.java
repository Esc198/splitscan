package com.splitscan.RestAPI.Security;

import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.stereotype.Component;

import lombok.Getter;
import lombok.Setter;

@Component
@ConfigurationProperties(prefix = "app.auth")
@Getter
@Setter
public class AuthProperties {

    private String jwtSecret;
    private long accessTokenTtlMinutes;
    private long refreshTokenTtlDays;
}
