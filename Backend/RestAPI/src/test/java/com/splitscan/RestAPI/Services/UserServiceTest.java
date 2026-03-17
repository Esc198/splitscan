package com.splitscan.RestAPI.Services;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import java.util.Optional;
import java.util.UUID;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Captor;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.http.HttpStatus;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.web.server.ResponseStatusException;

import com.splitscan.RestAPI.DTOs.user.UpdateMeRequestDTO;
import com.splitscan.RestAPI.DTOs.user.UserResponseDTO;
import com.splitscan.RestAPI.Models.User;
import com.splitscan.RestAPI.Repositories.UserRepository;

@ExtendWith(MockitoExtension.class)
class UserServiceTest {

    @Mock
    private UserRepository userRepository;

    @Mock
    private PasswordEncoder passwordEncoder;

    @Mock
    private RefreshTokenService refreshTokenService;

    @InjectMocks
    private UserService userService;

    @Captor
    private ArgumentCaptor<User> userCaptor;

    @Test
    void getCurrentUserReturnsAuthenticatedUsersData() {
        UUID currentUserId = UUID.randomUUID();
        User user = buildUser(currentUserId, "Enrique", "enrique@example.com", "hash");

        when(userRepository.findById(currentUserId)).thenReturn(Optional.of(user));

        UserResponseDTO response = userService.getCurrentUser(currentUserId);

        assertEquals(currentUserId, response.getId());
        assertEquals("Enrique", response.getName());
        assertEquals("enrique@example.com", response.getEmail());
    }

    @Test
    void updateCurrentUserUpdatesNameAndEmail() {
        UUID currentUserId = UUID.randomUUID();
        User user = buildUser(currentUserId, "Old Name", "old@example.com", "hash");
        UpdateMeRequestDTO request = new UpdateMeRequestDTO();
        request.setName("  Enrique  ");
        request.setEmail("  ENRIQUE@example.com ");

        when(userRepository.findById(currentUserId)).thenReturn(Optional.of(user));
        when(userRepository.findByEmailIgnoreCase("enrique@example.com")).thenReturn(Optional.empty());
        when(userRepository.save(any(User.class))).thenAnswer(invocation -> invocation.getArgument(0));

        UserResponseDTO response = userService.updateCurrentUser(currentUserId, request);

        verify(userRepository).save(userCaptor.capture());
        User savedUser = userCaptor.getValue();
        assertEquals("Enrique", savedUser.getName());
        assertEquals("enrique@example.com", savedUser.getEmail());
        assertEquals("Enrique", response.getName());
        assertEquals("enrique@example.com", response.getEmail());
        verify(refreshTokenService, never()).revokeAllActiveTokensForUser(currentUserId);
    }

    @Test
    void updateCurrentUserChangesPasswordAndRevokesAllRefreshTokens() {
        UUID currentUserId = UUID.randomUUID();
        User user = buildUser(currentUserId, "Enrique", "enrique@example.com", "old-hash");
        UpdateMeRequestDTO request = new UpdateMeRequestDTO();
        request.setCurrentPassword("old-password");
        request.setNewPassword("new-password");

        when(userRepository.findById(currentUserId)).thenReturn(Optional.of(user));
        when(passwordEncoder.matches("old-password", "old-hash")).thenReturn(true);
        when(passwordEncoder.encode("new-password")).thenReturn("new-hash");
        when(userRepository.save(any(User.class))).thenAnswer(invocation -> invocation.getArgument(0));

        UserResponseDTO response = userService.updateCurrentUser(currentUserId, request);

        verify(userRepository).save(userCaptor.capture());
        assertEquals("new-hash", userCaptor.getValue().getPassword());
        verify(refreshTokenService).revokeAllActiveTokensForUser(currentUserId);
        assertEquals(currentUserId, response.getId());
    }

    @Test
    void updateCurrentUserFailsWhenCurrentPasswordIsIncorrect() {
        UUID currentUserId = UUID.randomUUID();
        User user = buildUser(currentUserId, "Enrique", "enrique@example.com", "old-hash");
        UpdateMeRequestDTO request = new UpdateMeRequestDTO();
        request.setCurrentPassword("bad-password");
        request.setNewPassword("new-password");

        when(userRepository.findById(currentUserId)).thenReturn(Optional.of(user));
        when(passwordEncoder.matches("bad-password", "old-hash")).thenReturn(false);

        ResponseStatusException ex = assertThrows(ResponseStatusException.class,
                () -> userService.updateCurrentUser(currentUserId, request));

        assertEquals(HttpStatus.UNAUTHORIZED, ex.getStatusCode());
        verify(userRepository, never()).save(any(User.class));
        verify(refreshTokenService, never()).revokeAllActiveTokensForUser(currentUserId);
    }

    @Test
    void updateCurrentUserFailsWhenEmailAlreadyBelongsToAnotherUser() {
        UUID currentUserId = UUID.randomUUID();
        User user = buildUser(currentUserId, "Enrique", "old@example.com", "hash");
        UpdateMeRequestDTO request = new UpdateMeRequestDTO();
        request.setEmail("taken@example.com");

        when(userRepository.findById(currentUserId)).thenReturn(Optional.of(user));
        when(userRepository.findByEmailIgnoreCase("taken@example.com"))
                .thenReturn(Optional.of(buildUser(UUID.randomUUID(), "Other", "taken@example.com", "hash")));

        ResponseStatusException ex = assertThrows(ResponseStatusException.class,
                () -> userService.updateCurrentUser(currentUserId, request));

        assertEquals(HttpStatus.CONFLICT, ex.getStatusCode());
        verify(userRepository, never()).save(any(User.class));
    }

    @Test
    void deleteCurrentUserRevokesAllRefreshTokensAndDeletesUser() {
        UUID currentUserId = UUID.randomUUID();
        User user = buildUser(currentUserId, "Enrique", "enrique@example.com", "hash");

        when(userRepository.findById(currentUserId)).thenReturn(Optional.of(user));

        userService.deleteCurrentUser(currentUserId);

        verify(refreshTokenService).revokeAllActiveTokensForUser(currentUserId);
        verify(userRepository).delete(user);
    }

    private User buildUser(UUID id, String name, String email, String password) {
        User user = new User();
        user.setId(id);
        user.setName(name);
        user.setEmail(email);
        user.setPassword(password);
        return user;
    }
}
