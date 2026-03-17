package com.splitscan.RestAPI.Controllers;

import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import java.time.Instant;
import java.util.List;
import java.util.UUID;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;

import com.splitscan.RestAPI.Security.CurrentUserService;
import com.splitscan.RestAPI.Services.TransactionService;

@ExtendWith(MockitoExtension.class)
class TransactionControllerTest {

    @Mock
    private TransactionService transactionService;

    @Mock
    private CurrentUserService currentUserService;

    private MockMvc mockMvc;

    @BeforeEach
    void setUp() {
        TransactionController controller = new TransactionController(transactionService, currentUserService);
        mockMvc = MockMvcBuilders.standaloneSetup(controller).build();
    }

    @Test
    void getTransactionsParsesSinceQueryParamAsIsoDateTime() throws Exception {
        UUID currentUserId = UUID.randomUUID();
        UUID groupId = UUID.randomUUID();
        Instant since = Instant.parse("2026-03-16T10:30:00Z");

        when(currentUserService.requireCurrentUserId()).thenReturn(currentUserId);
        when(transactionService.getTransactions(currentUserId, groupId, since)).thenReturn(List.of());

        mockMvc.perform(get("/groups/{groupId}/transactions", groupId)
                .param("since", since.toString()))
                .andExpect(status().isOk());

        verify(transactionService).getTransactions(currentUserId, groupId, since);
    }

    @Test
    void getTransactionsReturnsBadRequestWhenSinceIsNotIsoDateTime() throws Exception {
        UUID groupId = UUID.randomUUID();

        mockMvc.perform(get("/groups/{groupId}/transactions", groupId)
                .param("since", "16-03-2026 10:30"))
                .andExpect(status().isBadRequest());

        verifyNoInteractions(transactionService);
        verifyNoInteractions(currentUserService);
    }
}
