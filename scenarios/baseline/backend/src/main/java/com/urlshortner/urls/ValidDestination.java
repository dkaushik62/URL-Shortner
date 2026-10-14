package com.urlshortner.urls;

import com.fasterxml.jackson.databind.JsonNode;
import jakarta.validation.Constraint;
import jakarta.validation.ConstraintValidator;
import jakarta.validation.ConstraintValidatorContext;
import jakarta.validation.Payload;
import java.lang.annotation.Retention;
import java.lang.annotation.Target;
import static java.lang.annotation.ElementType.*;
import static java.lang.annotation.RetentionPolicy.RUNTIME;

@Target({FIELD, PARAMETER, RECORD_COMPONENT, ANNOTATION_TYPE})
@Retention(RUNTIME)
@Constraint(validatedBy = ValidDestination.Validator.class)
public @interface ValidDestination {
    String message() default "url must be an HTTP or HTTPS destination without credentials or control characters";
    Class<?>[] groups() default {};
    Class<? extends Payload>[] payload() default {};

    class Validator implements ConstraintValidator<ValidDestination, JsonNode> {
        @Override
        public boolean isValid(JsonNode value, ConstraintValidatorContext context) {
            return value != null && value.isTextual() && Destination.valid(value.textValue());
        }
    }
}
