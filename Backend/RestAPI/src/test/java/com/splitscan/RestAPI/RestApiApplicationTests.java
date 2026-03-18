package com.splitscan.RestAPI;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.Map;

import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.ActiveProfiles;

@SpringBootTest
@ActiveProfiles("test")
class RestApiApplicationTests {

	private static final String[] REQUIRED_PROPERTIES = {
			"DB_URL",
			"DB_USER",
			"DB_PASSWORD",
			"JWT_SECRET",
			"JWT_ACCESS_TTL_MINUTES",
			"REFRESH_TOKEN_TTL_DAYS"
	};

	@AfterEach
	void clearProperties() {
		for (String propertyName : REQUIRED_PROPERTIES) {
			System.clearProperty(propertyName);
		}
	}

	@Test
	void contextLoads() {
	}

	@Test
	void applyRequiredPropertiesSetsResolvedValues() {
		Map<String, String> properties = Map.of(
				"DB_URL", "jdbc:h2:mem:testdb",
				"DB_USER", "sa",
				"DB_PASSWORD", "secret",
				"JWT_SECRET", "test-secret-value",
				"JWT_ACCESS_TTL_MINUTES", "15",
				"REFRESH_TOKEN_TTL_DAYS", "30");

		RestApiApplication.applyRequiredProperties(properties::get);

		assertEquals("test-secret-value", System.getProperty("JWT_SECRET"));
		assertEquals("15", System.getProperty("JWT_ACCESS_TTL_MINUTES"));
	}

	@Test
	void applyRequiredPropertiesThrowsWhenValuesAreMissing() {
		Map<String, String> properties = Map.of(
				"DB_URL", "jdbc:h2:mem:testdb",
				"DB_USER", "sa",
				"DB_PASSWORD", "secret");

		IllegalStateException exception = assertThrows(
				IllegalStateException.class,
				() -> RestApiApplication.applyRequiredProperties(properties::get));

		assertTrue(exception.getMessage().contains("JWT_SECRET"));
		assertTrue(exception.getMessage().contains("JWT_ACCESS_TTL_MINUTES"));
		assertTrue(exception.getMessage().contains("REFRESH_TOKEN_TTL_DAYS"));
	}

}
