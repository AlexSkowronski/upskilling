# 01 · Design patterns

## The idea

A design pattern is a named, reusable answer to a problem that keeps coming up. The name is
half the value: "put an adapter around it" tells a teammate a whole design in four words.
This topic implements 15 patterns in realistic Python, each with tests that show the
behaviour that matters, not just that the code runs.

## The problem it solves

Without patterns, the same problems get solved slightly differently every time: an
`if/elif` chain over provider names, vendor exceptions leaking into business logic, retry
loops copy-pasted around HTTP calls, an order's status checked in every method. Patterns
give each of these a standard, well-understood shape.

## How the code shows it

Each file opens with a docstring explaining the problem and what to notice. Then read its
test file in `tests/`: the tests are the clearest description of the behaviour.

| Pattern | Problem it solves | Code | Read for |
| --- | --- | --- | --- |
| **Creational** | | | |
| Factory (registry) | Choose a class at runtime by name | [`factory.py`](design_patterns/creational/factory.py) | Self-registering classes; no if/elif to edit |
| Builder | Assemble a complex object step by step | [`builder.py`](design_patterns/creational/builder.py) | Immutable builder; validation in `build()`; SQL params, not string formatting |
| **Structural** | | | |
| Adapter | Make a vendor API fit your interface | [`adapter.py`](design_patterns/structural/adapter.py) | Translating *errors*, not just method names |
| Decorator | Add behaviour around a call or object | [`decorator.py`](design_patterns/structural/decorator.py) | `@retry` with backoff + jitter, `@ttl_cache`, stackable object wrappers |
| Facade | One entry point to a fiddly subsystem | [`facade.py`](design_patterns/structural/facade.py) | Clean-up on failure: release stock if payment fails |
| Proxy | Control access to the real object | [`proxy.py`](design_patterns/structural/proxy.py) | Circuit breaker (closed → open → half-open) + stale fallback |
| Composite / Specification | Build complex rules from simple ones | [`composite.py`](design_patterns/structural/composite.py) | `&`, `\|`, `~` operators; `why_not()` explains failures |
| **Behavioural** | | | |
| Strategy | Swap algorithms at runtime | [`strategy.py`](design_patterns/behavioural/strategy.py) | Functions *and* classes as strategies; a strategy wrapping a strategy |
| Observer | React to events without coupling to the sender | [`observer.py`](design_patterns/behavioural/observer.py) | Typed events, base-class subscriptions, error isolation |
| Command | Actions as objects: undo, redo, queue | [`command.py`](design_patterns/behavioural/command.py) | Commands remember their own undo data; all-or-nothing macros |
| Chain of Responsibility | Pass a request along handlers | [`chain_of_responsibility.py`](design_patterns/behavioural/chain_of_responsibility.py) | Web-framework-style middleware; why order matters |
| State | Behaviour changes with state | [`state.py`](design_patterns/behavioural/state.py) | No if/elif on status; illegal transitions are impossible |
| Template Method vs pipeline | Fixed steps, variable details | [`template_method.py`](design_patterns/behavioural/template_method.py) | Same importer built by inheritance, then by composition |
| Iterator | Walk data without knowing how it's stored | [`iterator.py`](design_patterns/behavioural/iterator.py) | Lazy cursor pagination with generators |
| **Data access** | | | |
| Repository + Unit of Work | Keep SQL out of business logic; atomic changes | [`repository.py`](design_patterns/data/repository.py) | Rollback when a transfer fails half-way |

**Suggested reading order:** Strategy → Adapter → Decorator → Observer → Repository. These
five come up most often in real Python codebases. Then read the rest in any order.

### Python-specific notes

- Many patterns shrink in Python. A Strategy can be a plain function, a Factory a dict, an
  Iterator a generator, and a Decorator often just `@something`. The classic class-heavy
  versions come from languages without first-class functions.
- **Singleton is deliberately missing.** It's global state in disguise: hard to replace in
  tests and coupled to everything that uses it. In Python, create the object once at
  startup and pass it in. A module-level object (like `registry` in `factory.py`) is the
  lightweight alternative when you really want one shared instance.
- Time, randomness and I/O are always injected (`clock=`, `sleep=`, fakes), which is why
  all 100+ tests run in well under a second. That's Module 4's "functional core, imperative shell".

## Trade-offs

Every pattern adds indirection: more names, more files, more jumping around to follow
a call. Use a pattern when the problem it solves is **actually present**: a second
payment provider, a real need to undo, an API that really does fail. Code full of patterns
"for flexibility", with one implementation of each, is a classic over-engineering smell.

## Further reading

- [Python Design Patterns guide](https://python-patterns.guide/) by Brandon Rhodes: which
  classic patterns still matter in Python, and which the language makes unnecessary.
- [Refactoring.Guru: Design Patterns](https://refactoring.guru/design-patterns): clear
  diagrams for every pattern, useful as a quick reference.
