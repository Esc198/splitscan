package com.splitscan.RestAPI.Controllers;

import org.springframework.web.bind.annotation.RestController;

@RestController
public class GroupController {

	@GetMapping("/groups")
	public List<Group> getGroups() {
		// Logic to retrieve groups from the database
		return groupService.getAllGroups();
	}
	
}
