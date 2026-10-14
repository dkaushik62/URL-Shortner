package com.urlshortner.urls;

import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.NullAndEmptySource;
import org.junit.jupiter.params.provider.ValueSource;
import static org.junit.jupiter.api.Assertions.*;

class DestinationTest {
    @ParameterizedTest
    @ValueSource(strings = {
            "http://example.com", "https://example.com:8443/a?x=1#part",
            "HTTPS://example.com/path%20name", "http://localhost:8080/", "https://[::1]/"
    })
    void acceptsHttpDestinations(String value) {
        assertTrue(Destination.valid(value));
    }

    @ParameterizedTest
    @NullAndEmptySource
    @ValueSource(strings = {
            " ", "/relative", "ftp://example.com", "https:///path", "https://",
            "https://user@example.com", "https://user:password@example.com",
            "https://example.com/\r", "https://example.com/\n", "https://example.com/\t",
            "https://example.com/\u0000", "https://example.com/%0d", "https://example.com/%0A",
            "https://example.com/%7f", "https://example.com/%ZZ", "https://example.com:abc/",
            "https://example.com:65536/", "https://example.com:/", " https://example.com",
            "https://example.com\\@evil.example/", "https://bad host/"
    })
    void rejectsInvalidDestinations(String value) {
        assertFalse(Destination.valid(value));
    }
}
