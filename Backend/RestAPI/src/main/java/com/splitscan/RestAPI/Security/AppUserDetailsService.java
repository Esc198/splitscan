package com.splitscan.RestAPI.Security;

import java.util.UUID;

import org.springframework.security.core.userdetails.UserDetails;
import org.springframework.security.core.userdetails.UserDetailsService;
import org.springframework.security.core.userdetails.UsernameNotFoundException;
import org.springframework.stereotype.Service;

import com.splitscan.RestAPI.Models.User;
import com.splitscan.RestAPI.Repositories.UserRepository;

@Service
public class AppUserDetailsService implements UserDetailsService {

    private final UserRepository userRepository;

    public AppUserDetailsService(UserRepository userRepository) {
        this.userRepository = userRepository;
    }

    @Override
    public UserDetails loadUserByUsername(String email) throws UsernameNotFoundException {
        return userRepository.findByEmailIgnoreCase(email)
                .map(this::toPrincipal)
                .orElseThrow(() -> new UsernameNotFoundException("User not found with email: " + email));
    }

    public AuthenticatedUserPrincipal loadUserById(UUID userId) {
        return userRepository.findById(userId)
                .map(this::toPrincipal)
                .orElseThrow(() -> new UsernameNotFoundException("User not found with id: " + userId));
    }

    private AuthenticatedUserPrincipal toPrincipal(User user) {
        return new AuthenticatedUserPrincipal(user.getId(), user.getEmail(), user.getPassword());
    }
}
