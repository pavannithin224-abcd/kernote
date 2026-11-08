; TypeScript: declarations that define a module's shape.
(class_declaration name: (type_identifier) @name) @definition.class
(function_declaration name: (identifier) @name) @definition.function
(interface_declaration name: (type_identifier) @name) @definition.interface
(type_alias_declaration name: (type_identifier) @name) @definition.type
(enum_declaration name: (identifier) @name) @definition.enum

; `export const Foo = () => {}` and `const Foo = function () {}` are how most
; React components and hooks are declared, so they must count as definitions.
(lexical_declaration
  (variable_declarator
    name: (identifier) @name
    value: [(arrow_function) (function_expression)])) @definition.function

; Class methods. Without this a class's surface is invisible: the class is
; captured but none of its behaviour.
(method_definition name: (property_identifier) @name) @definition.method
