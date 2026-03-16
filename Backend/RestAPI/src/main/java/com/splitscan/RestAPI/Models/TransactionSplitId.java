package com.splitscan.RestAPI.Models;

import java.io.Serializable;
import java.util.UUID;

import lombok.Getter;
import lombok.Setter;

public class TransactionSplitId implements Serializable {

    /**
	 * 
	 */
	private static final long serialVersionUID = 1L;
	
	
	@Getter
	@Setter
	private UUID transaction;
    
	@Getter
	@Setter
	private UUID user;

}