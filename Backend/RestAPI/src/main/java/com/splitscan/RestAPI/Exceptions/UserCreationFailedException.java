package com.splitscan.RestAPI.Exceptions;

public class UserCreationFailedException extends RuntimeException {
    public UserCreationFailedException(String message) {
        super(message);
    }
}
