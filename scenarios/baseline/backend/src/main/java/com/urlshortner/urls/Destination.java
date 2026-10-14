package com.urlshortner.urls;

import java.net.URI;
import java.net.URISyntaxException;

final class Destination {
    private Destination() {}

    static boolean valid(String value) {
        if (value == null || value.isBlank()) return false;
        for (int i = 0; i < value.length(); i++) {
            char c = value.charAt(i);
            if (Character.isISOControl(c)) return false;
            if (c == '%' && i + 2 < value.length()) {
                int high = Character.digit(value.charAt(i + 1), 16);
                int low = Character.digit(value.charAt(i + 2), 16);
                if (high >= 0 && low >= 0 && Character.isISOControl((char) (high * 16 + low))) {
                    return false;
                }
            }
        }
        try {
            URI uri = new URI(value).parseServerAuthority();
            String scheme = uri.getScheme();
            if (!("http".equalsIgnoreCase(scheme) || "https".equalsIgnoreCase(scheme))) return false;
            if (uri.getHost() == null || uri.getHost().isBlank() || uri.getRawUserInfo() != null) return false;
            if (uri.getPort() < -1 || uri.getPort() > 65535) return false;
            // URI accepts an empty explicit port; reject it as malformed authority.
            return !uri.getRawAuthority().endsWith(":");
        } catch (URISyntaxException | IllegalArgumentException exception) {
            return false;
        }
    }
}
