; JavaScript: the TypeScript set minus the type-level declarations.
(class_declaration name: (identifier) @name) @definition.class
(function_declaration name: (identifier) @name) @definition.function
(lexical_declaration
  (variable_declarator
    name: (identifier) @name
    value: [(arrow_function) (function_expression)])) @definition.function

; Class methods. Without this a class's surface is invisible: the class is
; captured but none of its behaviour.
(method_definition name: (property_identifier) @name) @definition.method
