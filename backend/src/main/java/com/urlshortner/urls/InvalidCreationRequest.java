package com.urlshortner.urls;

/** Separates rejected creation input from programming/configuration failures. */
public final class InvalidCreationRequest extends IllegalArgumentException {
    public InvalidCreationRequest() {
        super("Invalid creation request");
    }
}
