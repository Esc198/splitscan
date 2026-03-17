package com.splitscan.RestAPI.Services;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import java.time.Instant;
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

import com.splitscan.RestAPI.DTOs.auth.AuthResponseDTO;
import com.splitscan.RestAPI.DTOs.auth.LoginRequestDTO;
import com.splitscan.RestAPI.DTOs.auth.LogoutRequestDTO;
import com.splitscan.RestAPI.DTOs.auth.RefreshRequestDTO;
import com.splitscan.RestAPI.DTOs.auth.RegisterRequestDTO;
import com.splitscan.RestAPI.Models.User;
import com.splitscan.RestAPI.Repositories.UserRepository;
import com.splitscan.RestAPI.Security.JwtService;

@ExtendWith(MockitoExtension.class)
class AuthServiceTest {

    @Mock
    private UserRepository userRepository;

    @Mock
    private PasswordEncoder passwordEncoder;

    @Mock
    private JwtService jwtService;

    @Mock
    private RefreshTokenService refreshTokenService;

    @InjectMocks
    private AuthService authService;

    @Captor
    private ArgumentCaptor<User> userCaptor;

    @Test
    void registerHashesPasswordAndReturnsTokens() {
        RegisterRequestDTO request = new RegisterRequestDTO();
        request.setName("  Enrique  ");
        request.setEmail("  ENRIQUE@example.com ");
        request.setPassword("secret123");

        Instant refreshExpiresAt = Instant.parse("2026-03-17T12:00:00Z");
        Instant accessExpiresAt = Instant.parse("2026-03-17T11:00:00Z");

        when(userRepository.findByEmailIgnoreCase("enrique@example.com")).thenReturn(Optional.empty());
        when(passwordEncoder.encode("secret123")).thenReturn("bcrypt-hash");
        when(userRepository.save(any(User.class))).thenAnswer(invocation -> invocation.getArgument(0));
        when(refreshTokenService.issueRefreshToken(any(User.class)))
                .thenReturn(new RefreshTokenService.IssuedRefreshToken("refresh-token", refreshExpiresAt));
        when(jwtService.issueAccessToken(any(User.class)))
                .thenReturn(new JwtService.IssuedAccessToken("access-token", accessExpiresAt));

        AuthResponseDTO response = authService.register(request);

        verify(userRepository).save(userCaptor.capture());
        User savedUser = userCaptor.getValue();
        assertNotNull(savedUser.getId());
        assertEquals("Enrique", savedUser.getName());
        assertEquals("enrique@example.com", savedUser.getEmail());
        assertEquals("bcrypt-hash", savedUser.getPassword());
        assertEquals("access-token", response.getAccessToken());
        assertEquals("refresh-token", response.getRefreshToken());
        assertEquals(accessExpiresAt, response.getAccessTokenExpiresAt());
        assertEquals("enrique@example.com", response.getUser().getEmail());
    }

    @Test
    void registerFailsWhenEmailAlreadyExists() {
        RegisterRequestDTO request = new RegisterRequestDTO();
        request.setName("Enrique");
        request.setEmail("enrique@example.com");
        request.setPassword("secret123");

        when(userRepository.findByEmailIgnoreCase("enrique@example.com"))
                .thenReturn(Optional.of(buildUser(UUID.randomUUID(), "Existing", "enrique@example.com", "hash")));

        ResponseStatusException ex = assertThrows(ResponseStatusException.class, () -> authService.register(request));

        assertEquals(HttpStatus.CONFLICT, ex.getStatusCode());
        verify(userRepository, never()).save(any(User.class));
        verify(refreshTokenService, never()).issueRefreshToken(any(User.class));
    }

    @Test
    void loginReturnsTokensWhenCredentialsAreValid() {
        LoginRequestDTO request = new LoginRequestDTO();
        request.setEmail("ENRIQUE@example.com");
        request.setPassword("secret123");
        User user = buildUser(UUID.randomUUID(), "Enrique", "enrique@example.com", "stored-hash");

        when(userRepository.findByEmailIgnoreCase("enrique@example.com")).thenReturn(Optional.of(user));
        when(passwordEncoder.matches("secret123", "stored-hash")).thenReturn(true);
        when(refreshTokenService.issueRefreshToken(user))
                .thenReturn(new RefreshTokenService.IssuedRefreshToken("refresh-token", Instant.parse("2026-03-17T12:00:00Z")));
        when(jwtService.issueAccessToken(user))
                .thenReturn(new JwtService.IssuedAccessToken("access-token", Instant.parse("2026-03-17T11:00:00Z")));

        AuthResponseDTO response = authService.login(request);

        assertEquals("access-token", response.getAccessToken());
        assertEquals("refresh-token", response.getRefreshToken());
        assertEquals(user.getId(), response.getUser().getId());
    }

    @Test
    void loginFailsWhenPasswordIsInvalid() {
        LoginRequestDTO request = new LoginRequestDTO();
        request.setEmail("enrique@example.com");
        request.setPassword("bad-password");
        User user = buildUser(UUID.randomUUID(), "Enrique", "enrique@example.com", "stored-hash");

        when(userRepository.findByEmailIgnoreCase("enrique@example.com")).thenReturn(Optional.of(user));
        when(passwordEncoder.matches("bad-password", "stored-hash")).thenReturn(false);

        ResponseStatusException ex = assertThrows(ResponseStatusException.class, () -> authService.login(request));

        assertEquals(HttpStatus.UNAUTHORIZED, ex.getStatusCode());
        verify(refreshTokenService, never()).issueRefreshToken(any(User.class));
    }

    @Test
    void refreshRotatesRefreshTokenAndIssuesNewAccessToken() {
        RefreshRequestDTO request = new RefreshRequestDTO();
        request.setRefreshToken("old-refresh-token");
        User user = buildUser(UUID.randomUUID(), "Enrique", "enrique@example.com", "stored-hash");
        RefreshTokenService.IssuedRefreshToken newRefreshToken = new RefreshTokenService.IssuedRefreshToken(
                "new-refresh-token",
                Instant.parse("2026-03-18T12:00:00Z"));

        when(refreshTokenService.rotateRefreshToken("old-refresh-token"))
                .thenReturn(new RefreshTokenService.RotatedRefreshToken(user, newRefreshToken));
        when(jwtService.issueAccessToken(user))
                .thenReturn(new JwtService.IssuedAccessToken("new-access-token", Instant.parse("2026-03-17T11:00:00Z")));

        AuthResponseDTO response = authService.refresh(request);

        assertEquals("new-access-token", response.getAccessToken());
        assertEquals("new-refresh-token", response.getRefreshToken());
        assertEquals(user.getId(), response.getUser().getId());
    }

    @Test
    void logoutRevokesRefreshToken() {
        LogoutRequestDTO request = new LogoutRequestDTO();
        request.setRefreshToken("refresh-token");

        authService.logout(request);

        verify(refreshTokenService).revokeRefreshToken("refresh-token");
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
