package com.splitscan.RestAPI.Security;

import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.UUID;

import org.springframework.security.oauth2.jose.jws.MacAlgorithm;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.security.oauth2.jwt.JwtClaimsSet;
import org.springframework.security.oauth2.jwt.JwtDecoder;
import org.springframework.security.oauth2.jwt.JwtEncoder;
import org.springframework.security.oauth2.jwt.JwtEncoderParameters;
import org.springframework.security.oauth2.jwt.JwtException;
import org.springframework.security.oauth2.jwt.JwsHeader;
import org.springframework.stereotype.Service;

import com.splitscan.RestAPI.Models.User;

@Service
public class JwtService {

    private final JwtEncoder jwtEncoder;
    private final JwtDecoder jwtDecoder;
    private final AuthProperties authProperties;

    public JwtService(JwtEncoder jwtEncoder, JwtDecoder jwtDecoder, AuthProperties authProperties) {
        this.jwtEncoder = jwtEncoder;
        this.jwtDecoder = jwtDecoder;
        this.authProperties = authProperties;
    }

    public IssuedAccessToken issueAccessToken(User user) {
        Instant issuedAt = Instant.now();
        Instant expiresAt = issuedAt.plus(authProperties.getAccessTokenTtlMinutes(), ChronoUnit.MINUTES);
        JwtClaimsSet claims = JwtClaimsSet.builder()
                .subject(user.getId().toString())
                .issuedAt(issuedAt)
                .expiresAt(expiresAt)
                .claim("email", user.getEmail())
                .claim("type", "access")
                .build();
        JwsHeader headers = JwsHeader.with(MacAlgorithm.HS256).build();
        String token = jwtEncoder.encode(JwtEncoderParameters.from(headers, claims)).getTokenValue();

        return new IssuedAccessToken(token, expiresAt);
    }

    public UUID extractUserId(String token) {
        Jwt jwt = jwtDecoder.decode(token);
        if (!"access".equals(jwt.getClaimAsString("type"))) {
            throw new JwtException("Invalid token type");
        }
        return UUID.fromString(jwt.getSubject());
    }

    public record IssuedAccessToken(String token, Instant expiresAt) {
    }
}
