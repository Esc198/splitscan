package com.splitscan.RestAPI;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.function.Function;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

import io.github.cdimascio.dotenv.Dotenv;

@SpringBootApplication
public class RestApiApplication {

	private static final List<String> REQUIRED_PROPERTIES = List.of(
			"DB_URL",
			"DB_USER",
			"DB_PASSWORD",
			"JWT_SECRET",
			"JWT_ACCESS_TTL_MINUTES",
			"REFRESH_TOKEN_TTL_DAYS");

	public static void main(String[] args) {
		Dotenv dotenv = Dotenv.configure()
				.ignoreIfMissing()
				.ignoreIfMalformed()
				.load();
		applyRequiredProperties(key -> resolveProperty(dotenv, key));

		SpringApplication.run(RestApiApplication.class, args);
	}

	static void applyRequiredProperties(Function<String, String> propertyResolver) {
		List<String> missingProperties = new ArrayList<>();
		Map<String, String> resolvedProperties = new LinkedHashMap<>();

		for (String propertyName : REQUIRED_PROPERTIES) {
			String propertyValue = propertyResolver.apply(propertyName);

			if (!hasText(propertyValue)) {
				missingProperties.add(propertyName);
				continue;
			}

			resolvedProperties.put(propertyName, propertyValue);
		}

		if (!missingProperties.isEmpty()) {
			throw new IllegalStateException(
					"Missing required configuration values: "
							+ String.join(", ", missingProperties)
							+ ". Define them as environment variables or in the .env file.");
		}

		resolvedProperties.forEach(System::setProperty);
	}

	private static String resolveProperty(Dotenv dotenv, String propertyName) {
		String systemProperty = System.getProperty(propertyName);
		if (hasText(systemProperty)) {
			return systemProperty;
		}

		String environmentVariable = System.getenv(propertyName);
		if (hasText(environmentVariable)) {
			return environmentVariable;
		}

		return dotenv.get(propertyName);
	}

	private static boolean hasText(String value) {
		return value != null && !value.isBlank();
	}

}
