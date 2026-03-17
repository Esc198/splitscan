package com.splitscan.RestAPI.Services;

import java.util.UUID;

import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.http.HttpStatus;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.server.ResponseStatusException;

import com.splitscan.RestAPI.DTOs.user.UpdateMeRequestDTO;
import com.splitscan.RestAPI.DTOs.user.UserResponseDTO;
import com.splitscan.RestAPI.Models.User;
import com.splitscan.RestAPI.Repositories.UserRepository;

@Service
public class UserService {

    private final UserRepository userRepository;
    private final PasswordEncoder passwordEncoder;
    private final RefreshTokenService refreshTokenService;

    public UserService(
            UserRepository userRepository,
            PasswordEncoder passwordEncoder,
            RefreshTokenService refreshTokenService) {
        this.userRepository = userRepository;
        this.passwordEncoder = passwordEncoder;
        this.refreshTokenService = refreshTokenService;
    }

    @Transactional(readOnly = true)
    public UserResponseDTO getCurrentUser(UUID currentUserId) {
        return toResponseDTO(getUserEntityById(currentUserId));
    }

    @Transactional
    public UserResponseDTO updateCurrentUser(UUID currentUserId, UpdateMeRequestDTO dto) {
        if (dto == null) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "User body is required");
        }

        User user = getUserEntityById(currentUserId);

        if (dto.getName() != null && !dto.getName().isBlank()) {
            user.setName(dto.getName().trim());
        }
        if (dto.getEmail() != null && !dto.getEmail().isBlank()) {
            String normalizedEmail = normalizeEmail(dto.getEmail());
            userRepository.findByEmailIgnoreCase(normalizedEmail).ifPresent(existing -> {
                if (!existing.getId().equals(currentUserId)) {
                    throw new ResponseStatusException(HttpStatus.CONFLICT, "Email already in use: " + normalizedEmail);
                }
            });
            user.setEmail(normalizedEmail);
        }

        updatePasswordIfRequested(user, dto);

        User updatedUser = userRepository.save(user);
        return toResponseDTO(updatedUser);
    }

    @Transactional
    public void deleteCurrentUser(UUID currentUserId) {
        User user = getUserEntityById(currentUserId);
        refreshTokenService.revokeAllActiveTokensForUser(currentUserId);

        try {
            userRepository.delete(user);
        } catch (DataIntegrityViolationException ex) {
            throw new ResponseStatusException(
                    HttpStatus.CONFLICT,
                    "User cannot be deleted while it is still referenced by other resources",
                    ex);
        }
    }

    private void updatePasswordIfRequested(User user, UpdateMeRequestDTO dto) {
        boolean currentPasswordProvided = dto.getCurrentPassword() != null && !dto.getCurrentPassword().isBlank();
        boolean newPasswordProvided = dto.getNewPassword() != null && !dto.getNewPassword().isBlank();

        if (!currentPasswordProvided && !newPasswordProvided) {
            return;
        }
        if (!currentPasswordProvided || !newPasswordProvided) {
            throw new ResponseStatusException(
                    HttpStatus.BAD_REQUEST,
                    "currentPassword and newPassword are both required to change the password");
        }
        if (!passwordEncoder.matches(dto.getCurrentPassword(), user.getPassword())) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "Current password is incorrect");
        }

        user.setPassword(passwordEncoder.encode(dto.getNewPassword()));
        refreshTokenService.revokeAllActiveTokensForUser(user.getId());
    }

    private User getUserEntityById(UUID id) {
        return userRepository.findById(id)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "User not found: " + id));
    }

    private UserResponseDTO toResponseDTO(User user) {
        return new UserResponseDTO(user.getId(), user.getName(), user.getEmail());
    }

    private String normalizeEmail(String email) {
        return email.trim().toLowerCase();
    }
}
