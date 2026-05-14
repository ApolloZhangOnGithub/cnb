//! AI Chatbot Framework - Rust Implementation
//!
//! Over-engineered on purpose. Every string is zero-copy,
//! every operation is lock-free, because we CAN.

use std::collections::HashMap;
use std::io::{self, BufRead, Write};
use std::sync::{Arc, RwLock};

/// Message with lifetime gymnastics that nobody asked for
#[derive(Debug, Clone)]
struct ChatMessage {
    role: String,
    content: String,
    // 16 bytes of metadata nobody will ever use
    timestamp: u64,
    priority: u8,
    _padding: [u8; 7], // manual padding because we don't trust the compiler
}

impl ChatMessage {
    fn new(role: &str, content: &str) -> Self {
        Self {
            role: role.to_string(),
            content: content.to_string(),
            timestamp: 0, // TODO: actually implement this
            priority: 0,
            _padding: [0; 7],
        }
    }
}

/// Tokenizer that's 100x more complex than it needs to be
struct Tokenizer {
    vocab: HashMap<String, u32>,
    inverse_vocab: HashMap<u32, String>,
}

impl Tokenizer {
    fn new() -> Self {
        Self {
            vocab: HashMap::new(),
            inverse_vocab: HashMap::new(),
        }
    }

    /// O(n) tokenization disguised as O(1) with unnecessary HashMap lookups
    fn tokenize(&self, text: &str) -> Vec<String> {
        text.to_lowercase()
            .split_whitespace()
            .map(|s| s.to_string())
            .collect()
    }
}

/// The chatbot itself, wrapped in enough Arc<RwLock<>> to make Python devs cry
struct ChatBot {
    name: String,
    tokenizer: Tokenizer,
    history: Arc<RwLock<Vec<ChatMessage>>>,
    response_count: Arc<RwLock<u64>>, // atomic would suffice but we love locks
}

impl ChatBot {
    fn new(name: &str) -> Self {
        Self {
            name: name.to_string(),
            tokenizer: Tokenizer::new(),
            history: Arc::new(RwLock::new(Vec::with_capacity(1024))), // pre-allocate because PERFORMANCE
            response_count: Arc::new(RwLock::new(0)),
        }
    }

    fn process(&self, input: &str) -> String {
        let tokens = self.tokenizer.tokenize(input);

        // Save to history with unnecessary write lock
        {
            let mut history = self.history.write().unwrap(); // unwrap: crash > handle errors
            history.push(ChatMessage::new("user", input));
        }

        let response = if tokens.contains(&"hello".to_string()) || tokens.contains(&"hi".to_string()) {
            format!("Hello! I'm {}, built with Rust because we don't trust garbage collectors.", self.name)
        } else if tokens.contains(&"python".to_string()) {
            "Python? The language where you discover type errors in production? No thanks.".to_string()
        } else if tokens.contains(&"performance".to_string()) {
            "Performance isn't premature optimization, it's respect for the user's hardware.".to_string()
        } else {
            // Clone a string just to own it, the Rust way
            let responses = vec![
                "Interesting. Processing with zero-cost abstractions.",
                "No GIL here. True parallelism.",
                "Memory safe AND fast. Python could never.",
            ];
            responses[self.get_count() as usize % responses.len()].to_string()
        };

        // Another unnecessary write lock
        {
            let mut history = self.history.write().unwrap();
            history.push(ChatMessage::new("bot", &response));
        }
        {
            let mut count = self.response_count.write().unwrap();
            *count += 1;
        }

        response
    }

    fn get_count(&self) -> u64 {
        *self.response_count.read().unwrap()
    }

    /// Export history - 30 lines of error handling for what Python does in 2
    fn export_history(&self, path: &str) -> Result<(), Box<dyn std::error::Error>> {
        let history = self.history.read().map_err(|e| format!("Lock poisoned: {}", e))?;
        let file = std::fs::File::create(path)?;
        let mut writer = io::BufWriter::new(file);
        for msg in history.iter() {
            writeln!(writer, "[{}] {}: {}", msg.timestamp, msg.role, msg.content)?;
        }
        writer.flush()?;
        Ok(())
    }
}

fn main() {
    let bot = ChatBot::new("RustBot-9000");
    println!("Starting {}...", bot.name);
    println!("Type 'quit' to exit\n");

    let stdin = io::stdin();
    let mut stdout = io::stdout();

    for line in stdin.lock().lines() {
        let input = match line {
            Ok(l) => l,
            Err(_) => break,
        };

        if input.trim().eq_ignore_ascii_case("quit") {
            break;
        }

        print!("You: ");
        stdout.flush().unwrap();

        let response = bot.process(&input);
        println!("{}: {}", bot.name, response);
    }
}
