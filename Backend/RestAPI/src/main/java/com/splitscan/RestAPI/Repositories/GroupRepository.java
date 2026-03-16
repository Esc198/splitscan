package com.splitscan.RestAPI.Repositories;

import java.util.List;
import java.util.UUID;

import org.springframework.data.jpa.repository.JpaRepository;

import com.splitscan.RestAPI.Models.Group;

public interface GroupRepository extends JpaRepository<Group, UUID> {

	List<Group> findGroupsForUser(UUID userId);
}