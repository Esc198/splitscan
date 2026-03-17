package com.splitscan.RestAPI.Services;

import java.util.UUID;

import org.springframework.http.HttpStatus;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.server.ResponseStatusException;

import com.splitscan.RestAPI.DTOs.auth.AuthResponseDTO;
import com.splitscan.RestAPI.DTOs.auth.LoginRequestDTO;
import com.splitscan.RestAPI.DTOs.auth.LogoutRequestDTO;
import com.splitscan.RestAPI.DTOs.auth.RefreshRequestDTO;
import com.splitscan.RestAPI.DTOs.auth.RegisterRequestDTO;
import com.splitscan.RestAPI.DTOs.user.UserResponseDTO;
import com.splitscan.RestAPI.Models.User;
import com.splitscan.RestAPI.Repositories.UserRepository;
import com.splitscan.RestAPI.Security.JwtService;
import com.splitscan.RestAPI.Security.JwtService.IssuedAccessToken;

@Service
public class AuthService {

    private final UserRepository userRepository;
    private final PasswordEncoder passwordEncoder;
    private final JwtService jwtService;
    private final RefreshTokenService refreshTokenService;

    public AuthService(
            UserRepository userRepository,
            PasswordEncoder passwordEncoder,
            JwtService jwtService,
            RefreshTokenService refreshTokenService) {
        this.userRepository = userRepository;
        this.passwordEncoder = passwordEncoder;
        this.jwtService = jwtService;
        this.refreshTokenService = refreshTokenService;
    }

    @Transactional
    public AuthResponseDTO register(RegisterRequestDTO dto) {
        String name = requireNonBlankText(dto == null ? null : dto.getName(), "name");
        String email = normalizeEmail(requireNonBlankText(dto == null ? null : dto.getEmail(), "email"));
        String password = requireNonBlankPassword(dto == null ? null : dto.getPassword(), "password");

        userRepository.findByEmailIgnoreCase(email).ifPresent(existing -> {
            throw new ResponseStatusException(HttpStatus.CONFLICT, "Email already in use: " + email);
        });

        User user = new User();
        user.setId(UUID.randomUUID());
        user.setName(name);
        user.setEmail(email);
        user.setPassword(passwordEncoder.encode(password));

        User savedUser = userRepository.save(user);
        RefreshTokenService.IssuedRefreshToken issuedRefreshToken = refreshTokenService.issueRefreshToken(savedUser);
        return buildAuthResponse(savedUser, issuedRefreshToken);
    }

    @Transactional(readOnly = true)
    public AuthResponseDTO login(LoginRequestDTO dto) {
        String email = normalizeEmail(requireNonBlankText(dto == null ? null : dto.getEmail(), "email"));
        String password = requireNonBlankPassword(dto == null ? null : dto.getPassword(), "password");

        User user = userRepository.findByEmailIgnoreCase(email)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.UNAUTHORIZED, "Invalid email or password"));

        if (!passwordEncoder.matches(password, user.getPassword())) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "Invalid email or password");
        }

        RefreshTokenService.IssuedRefreshToken issuedRefreshToken = refreshTokenService.issueRefreshToken(user);
        return buildAuthResponse(user, issuedRefreshToken);
    }

    @Transactional
    public AuthResponseDTO refresh(RefreshRequestDTO dto) {
        RefreshTokenService.RotatedRefreshToken rotatedRefreshToken = refreshTokenService.rotateRefreshToken(
                dto == null ? null : dto.getRefreshToken());
        return buildAuthResponse(rotatedRefreshToken.user(), rotatedRefreshToken.refreshToken());
    }

    @Transactional
    public void logout(LogoutRequestDTO dto) {
        refreshTokenService.revokeRefreshToken(dto == null ? null : dto.getRefreshToken());
    }

    private AuthResponseDTO buildAuthResponse(User user, RefreshTokenService.IssuedRefreshToken issuedRefreshToken) {
        IssuedAccessToken accessToken = jwtService.issueAccessToken(user);
        return new AuthResponseDTO(
                accessToken.token(),
                issuedRefreshToken.rawToken(),
                accessToken.expiresAt(),
                toUserResponseDTO(user));
    }

    private UserResponseDTO toUserResponseDTO(User user) {
        return new UserResponseDTO(user.getId(), user.getName(), user.getEmail());
    }

    private String requireNonBlankText(String value, String fieldName) {
        if (value == null || value.isBlank()) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, fieldName + " is required");
        }
        return value.trim();
    }

    private String requireNonBlankPassword(String value, String fieldName) {
        if (value == null || value.isBlank()) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, fieldName + " is required");
        }
        return value;
    }

    private String normalizeEmail(String email) {
        return email.trim().toLowerCase();
    }
}
