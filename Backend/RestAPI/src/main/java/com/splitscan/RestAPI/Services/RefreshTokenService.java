package com.splitscan.RestAPI.Services;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.Base64;
import java.util.HexFormat;
import java.util.List;
import java.util.UUID;
import java.security.SecureRandom;

import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.server.ResponseStatusException;

import com.splitscan.RestAPI.Models.RefreshToken;
import com.splitscan.RestAPI.Models.User;
import com.splitscan.RestAPI.Repositories.RefreshTokenRepository;
import com.splitscan.RestAPI.Security.AuthProperties;

@Service
public class RefreshTokenService {

    private static final SecureRandom SECURE_RANDOM = new SecureRandom();

    private final RefreshTokenRepository refreshTokenRepository;
    private final AuthProperties authProperties;

    public RefreshTokenService(RefreshTokenRepository refreshTokenRepository, AuthProperties authProperties) {
        this.refreshTokenRepository = refreshTokenRepository;
        this.authProperties = authProperties;
    }

    @Transactional
    public IssuedRefreshToken issueRefreshToken(User user) {
        String rawToken = generateRawToken();
        Instant createdAt = Instant.now();
        Instant expiresAt = createdAt.plus(authProperties.getRefreshTokenTtlDays(), ChronoUnit.DAYS);

        RefreshToken refreshToken = new RefreshToken();
        refreshToken.setId(UUID.randomUUID());
        refreshToken.setUser(user);
        refreshToken.setTokenHash(hashToken(rawToken));
        refreshToken.setCreatedAt(createdAt);
        refreshToken.setExpiresAt(expiresAt);

        refreshTokenRepository.save(refreshToken);
        return new IssuedRefreshToken(rawToken, expiresAt);
    }

    @Transactional
    public RotatedRefreshToken rotateRefreshToken(String rawToken) {
        RefreshToken existingToken = getActiveRefreshToken(rawToken);
        existingToken.setRevokedAt(Instant.now());
        refreshTokenRepository.save(existingToken);

        IssuedRefreshToken newRefreshToken = issueRefreshToken(existingToken.getUser());
        return new RotatedRefreshToken(existingToken.getUser(), newRefreshToken);
    }

    @Transactional
    public void revokeRefreshToken(String rawToken) {
        RefreshToken refreshToken = getActiveRefreshToken(rawToken);
        refreshToken.setRevokedAt(Instant.now());
        refreshTokenRepository.save(refreshToken);
    }

    @Transactional
    public void revokeAllActiveTokensForUser(UUID userId) {
        List<RefreshToken> activeTokens = refreshTokenRepository.findByUser_IdAndRevokedAtIsNullAndExpiresAtAfter(
                userId,
                Instant.now());
        if (activeTokens.isEmpty()) {
            return;
        }

        Instant revokedAt = Instant.now();
        activeTokens.forEach(token -> token.setRevokedAt(revokedAt));
        refreshTokenRepository.saveAll(activeTokens);
    }

    private RefreshToken getActiveRefreshToken(String rawToken) {
        String validatedToken = requireNonBlank(rawToken);
        RefreshToken refreshToken = refreshTokenRepository.findByTokenHash(hashToken(validatedToken))
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.UNAUTHORIZED, "Invalid refresh token"));

        if (refreshToken.getRevokedAt() != null) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "Refresh token has been revoked");
        }
        if (refreshToken.getExpiresAt().isBefore(Instant.now())) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "Refresh token has expired");
        }

        return refreshToken;
    }

    private String requireNonBlank(String rawToken) {
        if (rawToken == null || rawToken.isBlank()) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "refreshToken is required");
        }
        return rawToken.trim();
    }

    private String generateRawToken() {
        byte[] tokenBytes = new byte[32];
        SECURE_RANDOM.nextBytes(tokenBytes);
        return Base64.getUrlEncoder().withoutPadding().encodeToString(tokenBytes);
    }

    private String hashToken(String rawToken) {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            return HexFormat.of().formatHex(digest.digest(rawToken.getBytes(StandardCharsets.UTF_8)));
        } catch (NoSuchAlgorithmException ex) {
            throw new IllegalStateException("SHA-256 algorithm is not available", ex);
        }
    }

    public record IssuedRefreshToken(String rawToken, Instant expiresAt) {
    }

    public record RotatedRefreshToken(User user, IssuedRefreshToken refreshToken) {
    }
}
