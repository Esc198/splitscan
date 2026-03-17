package com.splitscan.RestAPI.Controllers;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.doAnswer;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;
import static org.springframework.http.MediaType.APPLICATION_JSON;
import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.authentication;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import java.time.Instant;
import java.util.List;
import java.util.UUID;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.HttpStatus;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.Authentication;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.web.server.ResponseStatusException;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc;

import com.splitscan.RestAPI.DTOs.auth.AuthResponseDTO;
import com.splitscan.RestAPI.DTOs.group.GroupResponseDTO;
import com.splitscan.RestAPI.DTOs.user.UserResponseDTO;
import com.splitscan.RestAPI.Security.AuthenticatedUserPrincipal;
import com.splitscan.RestAPI.Security.JwtAuthenticationFilter;
import com.splitscan.RestAPI.Services.AuthService;
import com.splitscan.RestAPI.Services.GroupService;
import com.splitscan.RestAPI.Services.TransactionService;
import com.splitscan.RestAPI.Services.UserService;

import jakarta.servlet.FilterChain;

@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.MOCK)
@AutoConfigureMockMvc
@ActiveProfiles("test")
class SecurityWebMvcTest {

    @Autowired
    private MockMvc mockMvc;

    @MockitoBean
    private AuthService authService;

    @MockitoBean
    private UserService userService;

    @MockitoBean
    private GroupService groupService;

    @MockitoBean
    private TransactionService transactionService;

    @MockitoBean
    private JwtAuthenticationFilter jwtAuthenticationFilter;

    @BeforeEach
    void setUp() throws Exception {
        doAnswer(invocation -> {
            FilterChain filterChain = invocation.getArgument(2);
            filterChain.doFilter(invocation.getArgument(0), invocation.getArgument(1));
            return null;
        }).when(jwtAuthenticationFilter).doFilter(any(), any(), any());
    }

    @Test
    void registerEndpointIsAccessibleWithoutAuthentication() throws Exception {
        when(authService.register(any())).thenReturn(buildAuthResponse());

        mockMvc.perform(post("/auth/register")
                .contentType(APPLICATION_JSON)
                .content("""
                        {
                          "name": "Enrique",
                          "email": "enrique@example.com",
                          "password": "secret123"
                        }
                        """))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.accessToken").value("access-token"));
    }

    @Test
    void refreshEndpointIsAccessibleWithoutAuthentication() throws Exception {
        when(authService.refresh(any())).thenReturn(buildAuthResponse());

        mockMvc.perform(post("/auth/refresh")
                .contentType(APPLICATION_JSON)
                .content("""
                        {
                          "refreshToken": "refresh-token"
                        }
                        """))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.refreshToken").value("refresh-token"));
    }

    @Test
    void logoutEndpointIsAccessibleWithoutAuthentication() throws Exception {
        mockMvc.perform(post("/auth/logout")
                .contentType(APPLICATION_JSON)
                .content("""
                        {
                          "refreshToken": "refresh-token"
                        }
                        """))
                .andExpect(status().isNoContent());
    }

    @Test
    void usersMeRequiresAuthentication() throws Exception {
        mockMvc.perform(get("/users/me"))
                .andExpect(status().isUnauthorized());

        verifyNoInteractions(userService);
    }

    @Test
    void groupsMineRequiresAuthentication() throws Exception {
        mockMvc.perform(get("/groups/mine"))
                .andExpect(status().isUnauthorized());

        verifyNoInteractions(groupService);
    }

    @Test
    void transactionsRequireAuthentication() throws Exception {
        mockMvc.perform(get("/groups/{groupId}/transactions", UUID.randomUUID()))
                .andExpect(status().isUnauthorized());

        verifyNoInteractions(transactionService);
    }

    @Test
    void groupsMineReturnsAuthenticatedUsersGroups() throws Exception {
        UUID currentUserId = UUID.randomUUID();
        UUID groupId = UUID.randomUUID();

        when(groupService.getMyGroups(currentUserId))
                .thenReturn(List.of(new GroupResponseDTO(groupId, "Viaje", Instant.parse("2026-03-16T10:00:00Z"), List.of())));

        mockMvc.perform(get("/groups/mine").with(authentication(authenticationFor(currentUserId))))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$[0].id").value(groupId.toString()))
                .andExpect(jsonPath("$[0].name").value("Viaje"));
    }

    @Test
    void userMeReturnsAuthenticatedUser() throws Exception {
        UUID currentUserId = UUID.randomUUID();

        when(userService.getCurrentUser(currentUserId))
                .thenReturn(new UserResponseDTO(currentUserId, "Enrique", "enrique@example.com"));

        mockMvc.perform(get("/users/me").with(authentication(authenticationFor(currentUserId))))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.id").value(currentUserId.toString()))
                .andExpect(jsonPath("$.email").value("enrique@example.com"));
    }

    @Test
    void groupEndpointReturnsForbiddenForAuthenticatedNonMember() throws Exception {
        UUID currentUserId = UUID.randomUUID();
        UUID groupId = UUID.randomUUID();

        when(groupService.getGroup(currentUserId, groupId))
                .thenThrow(new ResponseStatusException(HttpStatus.FORBIDDEN, "User is not a member of group"));

        mockMvc.perform(get("/groups/{groupId}", groupId).with(authentication(authenticationFor(currentUserId))))
                .andExpect(status().isForbidden());
    }

    private AuthResponseDTO buildAuthResponse() {
        return new AuthResponseDTO(
                "access-token",
                "refresh-token",
                Instant.parse("2026-03-17T11:00:00Z"),
                new UserResponseDTO(UUID.randomUUID(), "Enrique", "enrique@example.com"));
    }

    private Authentication authenticationFor(UUID userId) {
        AuthenticatedUserPrincipal principal = new AuthenticatedUserPrincipal(
                userId,
                "enrique@example.com",
                "hashed-password");
        return new UsernamePasswordAuthenticationToken(principal, null, principal.getAuthorities());
    }
}
