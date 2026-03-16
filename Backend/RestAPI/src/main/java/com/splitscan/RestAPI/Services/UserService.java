package com.splitscan.RestAPI.Services;

import java.util.UUID;

import org.springframework.stereotype.Service;

import com.splitscan.RestAPI.DTOs.user.UserRequestDTO;
import com.splitscan.RestAPI.DTOs.user.UserResponseDTO;
import com.splitscan.RestAPI.Exceptions.UnableUpdateUserException;
import com.splitscan.RestAPI.Exceptions.UserCreationFailedException;
import com.splitscan.RestAPI.Models.User;
import com.splitscan.RestAPI.Repositories.UserRepository;

@Service
public class UserService {

    private final UserRepository userRepository;

    public UserService(UserRepository userRepository) {
        this.userRepository = userRepository;
    }

    /**
     * Creates a new user from the given DTO.
     * Throws an exception if the email is already in use.
     */
    public UserResponseDTO createUser(UserRequestDTO dto) {
        userRepository.findByEmail(dto.getEmail()).ifPresent(u -> {
            throw new UserCreationFailedException("Email already in use: " + dto.getEmail());
        });

        User newUser = new User();
        newUser.setId(UUID.randomUUID());
        newUser.setName(dto.getName());
        newUser.setEmail(dto.getEmail());
        newUser.setPassword(dto.getPassword());

        User savedUser = userRepository.save(newUser);
        return toResponseDTO(savedUser);
    }

    /**
     * Retrieves a user by their UUID.
     */
    public UserResponseDTO getUserById(UUID id) {
        User user = userRepository.findById(id)
                .orElseThrow(() -> new RuntimeException("User not found: " + id));

        return toResponseDTO(user);
    }

    /**
     * Updates the name, email and/or password of an existing user.
     * Only the authenticated user should be able to call this.
     */
    public UserResponseDTO updateUser(UUID id, UserRequestDTO dto) {
        User user = getUserEntityById(id);

        if (dto.getName() != null && !dto.getName().isBlank()) {
            user.setName(dto.getName());
        }
        if (dto.getEmail() != null && !dto.getEmail().isBlank()) {
            // Check that the new email is not already taken by another account
            userRepository.findByEmail(dto.getEmail()).ifPresent(existing -> {
                if (!existing.getId().equals(id)) {
                    throw new UnableUpdateUserException("Email already in use: " + dto.getEmail());
                }
            });
            user.setEmail(dto.getEmail());
        }
        if (dto.getPassword() != null && !dto.getPassword().isBlank()) {
            user.setPassword(dto.getPassword());
        }

        User updatedUser = userRepository.save(user);
        return toResponseDTO(updatedUser);
    }

    /**
     * Deletes a user by their UUID.
     */
    public void deleteUser(UUID id) {
        User user = getUserEntityById(id); // ensures the user exists before deleting

        userRepository.delete(user);
    }

    private User getUserEntityById(UUID id) {
        return userRepository.findById(id)
                .orElseThrow(() -> new RuntimeException("User not found: " + id));
    }

    private UserResponseDTO toResponseDTO(User user) {
        return new UserResponseDTO(user.getId(), user.getName(), user.getEmail());
    }
}