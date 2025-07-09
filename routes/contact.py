from flask import Flask, render_template_string, Blueprint

# Create blueprint for contact page
contact_bp = Blueprint('contact', __name__, url_prefix='/contact')

# HTML template for contact page
contact_template = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Contact Us - Web3Fuel.io</title>
    
    <!-- Add EmailJS script -->
    <script src="https://cdn.jsdelivr.net/npm/@emailjs/browser@3/dist/email.min.js"></script>
    
    <style>
        :root {
            --primary: #00ffea;
            --secondary: #ff00ff;
            --accent: #7c3aed;
            --background: #000000;
            --card-bg: rgba(0, 0, 0, 0.7);
            --text: #ffffff;
            --text-muted: #a1a1aa;
            --border-color: #27272a;
            --success: #22c55e;
            --warning: #f59e0b;
        }
        
        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }
        
        body {
            background-color: var(--background);
            color: var(--text);
            font-family: 'Inter', 'Segoe UI', 'Helvetica Neue', sans-serif;
            margin: 0;
            overflow-x: hidden;
            position: relative;
            line-height: 1.5;
        }

        canvas {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            z-index: -1;
            opacity: 0.3;
        }

        .container {
            max-width: 70%;
            margin: 0 auto;
            padding: 0 1rem;
            position: relative;
            z-index: 1;
        }

        /* Header Styles - Same as marketing solutions */
        header {
            position: sticky;
            top: 0;
            z-index: 40;
            width: 100%;
            border-bottom: 1px solid var(--border-color);
            background: rgba(0, 0, 0, 0.95);
            backdrop-filter: blur(20px);
            box-shadow: 0 4px 20px rgba(0, 255, 234, 0.1);
        }

        .header-container {
            display: flex;
            height: 5rem;
            align-items: center;
            justify-content: space-between;
            max-width: 1650px;
            margin: 0 auto;
            padding: 0 1.5rem;
        }

        .logo {
            display: flex;
            align-items: center;
            gap: 0.75rem;
            transition: transform 0.3s ease;
            text-decoration: none;
            flex-shrink: 0;
            margin-right: auto;
        }

        .logo:hover {
            transform: scale(1.05);
        }

        .logo-icon {
            color: var(--secondary);
            font-size: 2rem;
            filter: drop-shadow(0 0 10px var(--secondary));
            animation: pulse 2s infinite;
        }

        .logo-text {
            font-size: 1.75rem;
            font-weight: bold;
            text-shadow: 0 0 15px var(--primary);
            background: linear-gradient(45deg, var(--primary), var(--secondary));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }

        .nav-desktop {
            display: none;
            align-items: center;
            gap: 0.5rem;
            margin-left: auto;
            flex-shrink: 0;
        }

        .nav-link {
            color: var(--text);
            text-decoration: none;
            font-size: 1rem;
            font-weight: 600;
            transition: all 0.3s ease;
            padding: 0.625rem 1rem;
            border-radius: 8px;
            position: relative;
            overflow: hidden;
            border: 1px solid transparent;
            background: rgba(255, 255, 255, 0.02);
            backdrop-filter: blur(10px);
            white-space: nowrap;
        }

        .nav-link::before {
            content: '';
            position: absolute;
            top: 0;
            left: -100%;
            width: 100%;
            height: 100%;
            background: linear-gradient(90deg, transparent, rgba(0, 255, 234, 0.2), transparent);
            transition: left 0.5s ease;
        }

        .nav-link:hover::before {
            left: 100%;
        }

        .nav-link:hover {
            color: var(--primary);
            border-color: var(--primary);
            box-shadow: 0 0 20px rgba(0, 255, 234, 0.3);
            transform: translateY(-2px);
            background: rgba(0, 255, 234, 0.1);
        }

        .nav-link.active {
            color: var(--background);
            background: var(--primary);
            border-color: var(--primary);
            box-shadow: 0 0 25px rgba(0, 255, 234, 0.5);
        }

        .nav-link.contact-highlight {
            padding: 0.75rem 1.25rem;
            border-radius: 8px;
            background-clip: padding-box;
            border: 2px solid transparent;
            position: relative;
            overflow: hidden;
        }

        .nav-link.contact-highlight::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            padding: 2px;
            background: linear-gradient(135deg, var(--primary), var(--secondary));
            border-radius: 8px;
            z-index: -1;
            -webkit-mask: 
                linear-gradient(#fff 0 0) content-box, 
                linear-gradient(#fff 0 0);
            -webkit-mask-composite: destination-out;
            mask-composite: subtract;
            box-sizing: border-box;
        }

        .nav-link.contact-highlight:hover {
            background: linear-gradient(135deg, rgba(0, 255, 234, 0.2), rgba(255, 0, 255, 0.2));
            color: var(--primary);
            box-shadow: 0 0 30px rgba(0, 255, 234, 0.3);
            transform: translateY(-2px);
        }

        .menu-button {
            background: rgba(0, 255, 234, 0.1);
            border: 2px solid var(--primary);
            color: var(--primary);
            cursor: pointer;
            font-size: 1.25rem;
            padding: 0.625rem;
            border-radius: 8px;
            transition: all 0.3s ease;
            backdrop-filter: blur(10px);
            flex-shrink: 0;
        }

        .menu-button:hover {
            background: var(--primary);
            color: var(--background);
            transform: scale(1.1);
            box-shadow: 0 0 20px rgba(0, 255, 234, 0.4);
        }

        @keyframes pulse {
            0%, 100% {
                filter: drop-shadow(0 0 10px var(--secondary));
            }
            50% {
                filter: drop-shadow(0 0 20px var(--secondary));
            }
        }

        /* Contact Page Specific Styles */
        .contact-hero {
            padding: 3rem 0 1.5rem 0;
            text-align: center;
        }

        .contact-subtitle {
            font-size: 1.6rem;
            color: #e2e8f0;
            max-width: 40rem;
            margin: 0 auto 1.5rem auto;
            line-height: 1.6;
            font-weight: 600;
        }

        .contact-form-container {
            display: flex;
            justify-content: center;
            margin-bottom: 4rem;
        }

        .contact-form-section {
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 1rem;
            padding: 2rem;
            max-width: 700px;
            width: 100%;
        }

        .form-title {
            font-size: 1.5rem;
            color: var(--primary);
            margin-bottom: 1rem;
            text-align: center;
        }

        .form-description {
            color: var(--text-muted);
            text-align: center;
            margin-bottom: 2rem;
            line-height: 1.6;
        }

        .contact-form {
            max-width: 100%;
        }

        .appointment-toggle {
            display: flex;
            align-items: center;
            gap: 0.75rem;
            margin-bottom: 2rem;
            padding: 1rem;
            background: rgba(0, 255, 234, 0.05);
            border: 1px solid rgba(0, 255, 234, 0.2);
            border-radius: 0.5rem;
        }

        .toggle-checkbox {
            width: 1.25rem;
            height: 1.25rem;
            accent-color: var(--primary);
            cursor: pointer;
        }

        .toggle-label {
            color: var(--text);
            font-size: 1rem;
            font-weight: 500;
            cursor: pointer;
        }

        .form-group {
            margin-bottom: 1.5rem;
        }

        .form-label {
            display: block;
            margin-bottom: 0.5rem;
            color: #e2e8f0;
            font-size: 0.875rem;
            font-weight: 500;
        }

        .form-input {
            width: 100%;
            padding: 0.875rem;
            background: rgba(0, 0, 0, 0.2);
            border: 1px solid var(--border-color);
            border-radius: 0.375rem;
            color: white;
            font-size: 1rem;
            transition: border-color 0.2s;
        }

        .form-input:focus {
            outline: none;
            border-color: var(--primary);
            box-shadow: 0 0 0 2px rgba(0, 255, 234, 0.1);
        }

        .form-input::placeholder {
            color: var(--text-muted);
        }

        /* Fixed dropdown styling */
        select.form-input {
            background: rgba(0, 0, 0, 0.8);
            color: white;
        }

        select.form-input option {
            background: rgba(0, 0, 0, 0.95);
            color: white;
            padding: 0.5rem;
        }

        select.form-input option:hover {
            background: rgba(0, 255, 234, 0.2);
        }

        .form-textarea {
            min-height: 120px;
            resize: vertical;
        }

        .appointment-fields {
            display: none;
            background: rgba(0, 255, 234, 0.05);
            border: 1px solid rgba(0, 255, 234, 0.2);
            border-radius: 0.5rem;
            padding: 1.5rem;
            margin-bottom: 1.5rem;
        }

        .appointment-fields.show {
            display: block;
        }

        .appointment-header {
            color: var(--primary);
            font-size: 1.1rem;
            font-weight: 600;
            margin-bottom: 1rem;
            text-align: center;
        }

        /* Date/time picker styling */
        input[type="datetime-local"] {
            cursor: pointer;
            position: relative;
            color: #a1a1aa;
        }

        input[type="datetime-local"]::-webkit-calendar-picker-indicator {
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            width: auto;
            height: auto;
            background: transparent;
            cursor: pointer;
        }

        input[type="datetime-local"]:focus {
            color: white;
        }

        input[type="datetime-local"]:valid {
            color: white;
        }

        .form-submit {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            padding: 1rem 2rem;
            background: linear-gradient(45deg, var(--primary), var(--secondary));
            color: black;
            font-weight: 600;
            border-radius: 0.375rem;
            cursor: pointer;
            border: none;
            transition: all 0.3s ease;
            width: 100%;
            font-size: 1.1rem;
            margin-top: 1rem;
        }

        .form-submit:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 25px rgba(0, 255, 234, 0.3);
        }

        .form-submit:disabled {
            opacity: 0.6;
            cursor: not-allowed;
            transform: none;
        }

        /* Success/Error Message Styles */
        .alert {
            padding: 1rem;
            border-radius: 0.5rem;
            margin-bottom: 1rem;
            display: none;
        }

        .alert-success {
            background: rgba(34, 197, 94, 0.1);
            border: 1px solid rgba(34, 197, 94, 0.3);
            color: #22c55e;
        }

        .alert-error {
            background: rgba(239, 68, 68, 0.1);
            border: 1px solid rgba(239, 68, 68, 0.3);
            color: #ef4444;
        }

        .alert.show {
            display: block;
        }

        /* Footer Styles - Same as marketing solutions but without bottom */
        .custom-footer {
            background: rgba(0, 0, 0, 0.7);
            padding: 3rem 0 2rem 0;
            text-align: center;
            margin-top: 3rem;
            border-top: 1px solid var(--border-color);
        }

        .footer-content {
            max-width: 1200px;
            margin: 0 auto;
            padding: 0 1rem;
        }

        .footer-main {
            display: flex;
            flex-direction: column;
            gap: 3rem;
            margin-bottom: 2rem;
        }

        .social-section {
            flex: 1;
            text-align: center;
        }

        .social-title {
            color: #ffffff;
            font-size: 1.3rem;
            font-weight: 600;
            margin-bottom: 1rem;
        }

        .social-links {
            display: flex;
            flex-wrap: wrap;
            align-items: center;
            justify-content: center;
            gap: 2rem;
        }

        .social-links a {
            transition: all 0.3s ease;
            margin: 5px;
        }

        .social-links a:hover {
            transform: scale(1.2);
            filter: drop-shadow(0 0 15px #00ffea);
        }

        .social-links svg {
            transition: fill 0.3s ease;
        }

        .social-links a:hover svg {
            fill: #00ffea !important;
        }

        .newsletter-section {
            flex: 1;
            text-align: center;
        }

        .newsletter-title {
            color: #ffffff;
            font-size: 1.3rem;
            font-weight: 600;
            margin-bottom: 1rem;
        }

        .newsletter-form {
            display: flex;
            flex-direction: column;
            gap: 1rem;
            max-width: 400px;
            margin: 0 auto;
        }

        .newsletter-input {
            padding: 0.75rem;
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid #27272a;
            border-radius: 0.375rem;
            color: #ffffff;
            font-size: 0.875rem;
            transition: border-color 0.3s ease;
            text-align: center;
        }

        .newsletter-input::placeholder {
            color: #a1a1aa;
            text-align: center;
        }

        .newsletter-input:focus {
            outline: none;
            border-color: #00ffea;
            box-shadow: 0 0 10px rgba(0, 255, 234, 0.2);
        }

        .newsletter-button {
            background: #00ffea;
            color: #000000;
            border: none;
            padding: 0.75rem 1.5rem;
            border-radius: 0.375rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
        }

        .newsletter-button:hover {
            background: #00d6c4;
            transform: translateY(-2px);
            box-shadow: 0 4px 15px rgba(0, 255, 234, 0.3);
        }

        /* Animations */
        @keyframes gradientShift {
            0% {
                background-position: 0% 50%;
            }
            50% {
                background-position: 100% 50%;
            }
            100% {
                background-position: 0% 50%;
            }
        }

        /* Media Queries */
        @media (min-width: 640px) {
            .newsletter-form {
                flex-direction: row;
            }
            
            .newsletter-input {
                flex: 1;
            }
        }

        @media (min-width: 768px) {
            .nav-desktop {
                display: flex;
            }
            
            .menu-button {
                display: none;
            }

            .footer-main {
                flex-direction: row;
                align-items: flex-start;
            }
        }

        @media (min-width: 1200px) {
            .nav-desktop {
                gap: 0.75rem;
            }
        }

        @media (min-width: 1920px) {
            .container {
                max-width: 1600px;
            }
        }

        @media (max-width: 767px) {
            .contact-form-section {
                margin: 0 1rem;
            }

            .social-links {
                gap: 1.5rem;
            }
        }
    </style>
</head>
<body>
    <canvas id="matrix"></canvas>
    
    <!-- Header -->
    <header>
        <div class="header-container">
            <a href="/" class="logo">
                <span class="logo-icon">🚀</span>
                <span class="logo-text">Web3Fuel.io</span>
            </a>
            
            <nav class="nav-desktop">
                <a href="/trading-suite" class="nav-link">Trading Suite</a>
                <a href="/marketing-solutions" class="nav-link">Marketing Solutions</a>
                <a href="/blog" class="nav-link">Blog</a>
                <a href="/contact" class="nav-link contact-highlight active">Contact</a>
            </nav>
            
            <button class="menu-button" id="menu-button">☰</button>
        </div>
    </header>
    
    <!-- Contact Hero Section -->
    <section class="contact-hero">
        <div class="container">
            <p class="contact-subtitle">Fill out the form below to reach out and we'll respond as quickly as possible via email response.</p>
        </div>
    </section>
    
    <!-- Contact Form -->
    <section class="contact-content">
        <div class="container">
            <div class="contact-form-container">
                <div class="contact-form-section">
                    <h3 class="form-title">Send Us a Message</h3>
                    <p class="form-description">Whether you need AI trading tools or marketing solutions, <br>let's discuss how we can help accelerate your success:</p>
                    
                    <div id="alert-container"></div>
                    
                    <form class="contact-form" id="contactForm" onsubmit="sendEmail(event)">
                        <!-- Appointment Toggle -->
                        <div class="appointment-toggle">
                            <input type="checkbox" id="appointmentToggle" class="toggle-checkbox" onchange="toggleAppointmentFields()">
                            <label for="appointmentToggle" class="toggle-label">Click here to schedule an appointment during this inquiry</label>
                        </div>

                        <div class="form-group">
                            <label for="name" class="form-label">Full Name *</label>
                            <input type="text" id="name" name="name" class="form-input" placeholder="Enter your full name" required>
                        </div>
                        
                        <div class="form-group">
                            <label for="email" class="form-label">Email Address *</label>
                            <input type="email" id="email" name="email" class="form-input" placeholder="your.email@example.com" required>
                        </div>
                        
                        <div class="form-group">
                            <label for="company" class="form-label">Company (Optional)</label>
                            <input type="text" id="company" name="company" class="form-input" placeholder="Your company name">
                        </div>
                        
                        <div class="form-group">
                            <label for="subject" class="form-label">Subject *</label>
                            <select id="subject" name="subject" class="form-input" required>
                                <option value="">Select a topic...</option>
                                <option value="Trading Tools Inquiry">Trading Tools & Market Analysis</option>
                                <option value="Marketing Solutions Inquiry">AI Marketing Solutions</option>
                                <option value="Partnership Opportunity">Partnership Opportunity</option>
                                <option value="General Question">General Question</option>
                                <option value="Technical Support">Technical Support</option>
                                <option value="Other">Other</option>
                            </select>
                        </div>

                        <!-- Appointment Fields (Hidden by default) -->
                        <div class="appointment-fields" id="appointmentFields">
                            <div class="appointment-header">📅 Schedule Your Meeting</div>
                            <div class="form-group">
                                <label for="datetime" class="form-label">Preferred Date & Time (EST) *</label>
                                <input type="datetime-local" id="datetime" name="datetime" class="form-input">
                            </div>
                        </div>
                        
                        <div class="form-group">
                            <label for="message" class="form-label">Message *</label>
                            <textarea id="message" name="message" class="form-input form-textarea" placeholder="Tell us about your project, goals, or any specific questions you have..." required></textarea>
                        </div>
                        
                        <button type="submit" class="form-submit" id="submitBtn">
                            Send Message
                        </button>
                    </form>
                </div>
            </div>
        </div>
    </section>

    <!-- Footer -->
    <footer class="custom-footer">
        <div class="footer-content">
            <!-- Main Footer Content -->
            <div class="footer-main">
                <!-- Social Media Section (Left) -->
                <div class="social-section">
                    <h3 class="social-title">Follow Here</h3>
                    <div class="social-links">
                        <!-- YouTube -->
                        <a href="https://www.youtube.com/@web3fuel/" target="_blank" rel="noopener noreferrer" style="text-decoration:none;border:0;width:50px;height:50px;padding:2px;margin:5px;color:#11CBE9;border-radius:50%;background-color:#000000;">
                            <svg class="niftybutton-youtube" style="display:block;fill:currentColor" data-donate="true" data-tag="you" data-name="YouTube" viewBox="0 0 512 512" preserveAspectRatio="xMidYMid meet">
                                <title>YouTube social icon</title>
                                <path d="M422.6 193.6c-5.3-45.3-23.3-51.6-59-54 -50.8-3.5-164.3-3.5-215.1 0 -35.7 2.4-53.7 8.7-59 54 -4 33.6-4 91.1 0 124.8 5.3 45.3 23.3 51.6 59 54 50.9 3.5 164.3 3.5 215.1 0 35.7-2.4 53.7-8.7 59-54C426.6 284.8 426.6 227.3 422.6 193.6zM222.2 303.4v-94.6l90.7 47.3L222.2 303.4z"></path>
                            </svg>
                        </a>
                        
                        <!-- LinkedIn -->
                        <a href="https://www.linkedin.com/in/web3fuel/" target="_blank" rel="noopener noreferrer" style="text-decoration:none;border:0;width:45px;height:45px;padding:2px;margin:5px;color:#11CBE9;border-radius:50%;background-color:#000000;">
                            <svg class="niftybutton-linkedin" style="display:block;fill:currentColor" data-donate="true" data-tag="lin" data-name="LinkedIn" viewBox="0 0 512 512" preserveAspectRatio="xMidYMid meet">
                                <title>LinkedIn social icon</title>
                                <path d="M186.4 142.4c0 19-15.3 34.5-34.2 34.5 -18.9 0-34.2-15.4-34.2-34.5 0-19 15.3-34.5 34.2-34.5C171.1 107.9 186.4 123.4 186.4 142.4zM181.4 201.3h-57.8V388.1h57.8V201.3zM273.8 201.3h-55.4V388.1h55.4c0 0 0-69.3 0-98 0-26.3 12.1-41.9 35.2-41.9 21.3 0 31.5 15 31.5 41.9 0 26.9 0 98 0 98h57.5c0 0 0-68.2 0-118.3 0-50-28.3-74.2-68-74.2 -39.6 0-56.3 30.9-56.3 30.9v-25.2H273.8z"></path>
                            </svg>
                        </a>
                        
                        <!-- TikTok -->
                        <a href="https://www.tiktok.com/@web3fuel/" target="_blank" rel="noopener noreferrer" style="text-decoration:none;border:0;width:42px;height:42px;padding:2px;margin:5px;color:#11CBE9;border-radius:50%;background-color:#000000;">
                            <svg class="niftybutton-tiktok" style="display:block;fill:currentColor" data-donate="true" data-tag="tic" data-name="TikTok" viewBox="0 0 512 512" preserveAspectRatio="xMidYMid meet">
                                <title>TikTok social icon</title>
                                <path d="M 386.160156 141.550781 C 383.457031 140.15625 380.832031 138.625 378.285156 136.964844 C 370.878906 132.070312 364.085938 126.300781 358.058594 119.785156 C 342.976562 102.523438 337.339844 85.015625 335.265625 72.757812 L 335.351562 72.757812 C 333.617188 62.582031 334.332031 56 334.441406 56 L 265.742188 56 L 265.742188 321.648438 C 265.742188 325.214844 265.742188 328.742188 265.589844 332.226562 C 265.589844 332.660156 265.550781 333.058594 265.523438 333.523438 C 265.523438 333.714844 265.523438 333.917969 265.484375 334.117188 C 265.484375 334.167969 265.484375 334.214844 265.484375 334.265625 C 264.011719 353.621094 253.011719 370.976562 236.132812 380.566406 C 227.472656 385.496094 217.675781 388.078125 207.707031 388.066406 C 175.699219 388.066406 149.757812 361.964844 149.757812 329.734375 C 149.757812 297.5 175.699219 271.398438 207.707031 271.398438 C 213.765625 271.394531 219.789062 272.347656 225.550781 274.226562 L 225.632812 204.273438 C 190.277344 199.707031 154.621094 210.136719 127.300781 233.042969 C 115.457031 243.328125 105.503906 255.605469 97.882812 269.316406 C 94.984375 274.316406 84.042969 294.410156 82.714844 327.015625 C 81.882812 345.523438 87.441406 364.699219 90.089844 372.625 L 90.089844 372.792969 C 91.757812 377.457031 98.214844 393.382812 108.742188 406.808594 C 117.230469 417.578125 127.253906 427.035156 138.5 434.882812 L 138.5 434.714844 L 138.667969 434.882812 C 171.925781 457.484375 208.800781 456 208.800781 456 C 215.183594 455.742188 236.566406 456 260.851562 444.492188 C 287.785156 431.734375 303.117188 412.726562 303.117188 412.726562 C 312.914062 401.367188 320.703125 388.425781 326.148438 374.449219 C 332.367188 358.109375 334.441406 338.507812 334.441406 330.675781 L 334.441406 189.742188 C 335.273438 190.242188 346.375 197.582031 346.375 197.582031 C 346.375 197.582031 362.367188 207.832031 387.316406 214.507812 C 405.214844 219.257812 429.332031 220.257812 429.332031 220.257812 L 429.332031 152.058594 C 420.882812 152.976562 403.726562 150.308594 386.160156 141.550781 Z M 386.160156 141.550781"></path>
                            </svg>
                        </a>
                        
                        <!-- X (Twitter) -->
                        <a href="https://x.com/web3fuel/" target="_blank" rel="noopener noreferrer" style="text-decoration:none;border:0;width:40px;height:40px;padding:2px;margin:5px;color:#11CBE9;border-radius:50%;background-color:#000000;">
                            <svg class="niftybutton-twitterx" style="display:block;fill:currentColor" data-donate="true" data-tag="twix" data-name="TwitterX" viewBox="0 0 512 512" preserveAspectRatio="xMidYMid meet">
                                <title>Twitter X social icon</title>
                                <path d="M 304.757 216.824 L 495.394 0 L 450.238 0 L 284.636 188.227 L 152.475 0 L 0 0 L 199.902 284.656 L 0 512 L 45.16 512 L 219.923 313.186 L 359.525 512 L 512 512 M 61.456 33.322 L 130.835 33.322 L 450.203 480.317 L 380.811 480.317 "></path>
                            </svg>
                        </a>
                    </div>
                </div>

                <!-- Newsletter Section (Right) -->
                <div class="newsletter-section">
                    <h3 class="newsletter-title">Signup for AI Tips & Industry Insights</h3>
                    <form class="newsletter-form" onsubmit="event.preventDefault(); alert('Newsletter signup coming soon!');">
                        <input 
                            type="email" 
                            class="newsletter-input" 
                            placeholder="Enter your email address" 
                            required
                        >
                        <button type="submit" class="newsletter-button">
                            Subscribe
                        </button>
                    </form>
                </div>
            </div>
        </div>
    </footer>

    <script>
        // Matrix Canvas Background - Same as homepage
        const canvas = document.getElementById('matrix');
        const ctx = canvas.getContext('2d');

        canvas.width = window.innerWidth;
        canvas.height = window.innerHeight;

        const letters = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ';
        const fontSize = 16;
        const columns = canvas.width / fontSize;

        const drops = [];
        for (let i = 0; i < columns; i++) {
            drops[i] = Math.floor(Math.random() * canvas.height / fontSize);
        }

        function draw() {
            ctx.fillStyle = 'rgba(0, 0, 0, 0.05)';
            ctx.fillRect(0, 0, canvas.width, canvas.height);

            ctx.fillStyle = '#00ffea';
            ctx.font = fontSize + 'px Courier New';

            for (let i = 0; i < drops.length; i++) {
                const text = letters[Math.floor(Math.random() * letters.length)];
                ctx.fillText(text, i * fontSize, drops[i] * fontSize);

                if (drops[i] * fontSize > canvas.height && Math.random() > 0.975) {
                    drops[i] = 0;
                }

                drops[i] += 0.5;
            }
        }

        setInterval(draw, 50);

        window.addEventListener('resize', () => {
            canvas.width = window.innerWidth;
            canvas.height = window.innerHeight;
        });

        // Mobile Menu Toggle
        const menuButton = document.getElementById('menu-button');
        
        if (menuButton) {
            menuButton.addEventListener('click', () => {
                console.log('Mobile menu clicked');
            });
        }

        // Toggle appointment fields
        function toggleAppointmentFields() {
            const checkbox = document.getElementById('appointmentToggle');
            const fields = document.getElementById('appointmentFields');
            const datetimeInput = document.getElementById('datetime');
            
            if (checkbox.checked) {
                fields.classList.add('show');
                datetimeInput.required = true;
                
                // Set minimum date to today for datetime picker
                const now = new Date();
                now.setMinutes(now.getMinutes() - now.getTimezoneOffset());
                datetimeInput.min = now.toISOString().slice(0, 16);
            } else {
                fields.classList.remove('show');
                datetimeInput.required = false;
                datetimeInput.value = '';
            }
        }

        // Alert Functions
        function showAlert(message, type) {
            const alertContainer = document.getElementById('alert-container');
            const alert = document.createElement('div');
            alert.className = `alert alert-${type} show`;
            alert.textContent = message;
            
            alertContainer.innerHTML = '';
            alertContainer.appendChild(alert);
            
            setTimeout(() => {
                alert.classList.remove('show');
                setTimeout(() => alertContainer.innerHTML = '', 300);
            }, 5000);
        }

        // Contact form submission with EmailJS
        function sendEmail(event) {
            event.preventDefault();
            
            const submitBtn = document.getElementById('submitBtn');
            const originalText = submitBtn.textContent;
            
            // Disable button and show loading state
            submitBtn.disabled = true;
            submitBtn.textContent = 'Sending...';
            
            // Initialize EmailJS with your public key
            emailjs.init("xSYgQUruN6qY2C0o2");
            
            // Check if appointment is requested
            const appointmentRequested = document.getElementById('appointmentToggle').checked;
            let estDateTime = 'No appointment requested';
            
            if (appointmentRequested) {
                const datetimeInput = document.getElementById('datetime').value;
                if (datetimeInput) {
                    const selectedDate = new Date(datetimeInput);
                    estDateTime = selectedDate.toLocaleString("en-US", {
                        timeZone: "America/New_York",
                        year: 'numeric',
                        month: 'long',
                        day: 'numeric',
                        hour: 'numeric',
                        minute: '2-digit',
                        hour12: true
                    }) + " EST";
                }
            }
            
            const params = {
                name: document.getElementById('name').value,
                email: document.getElementById('email').value,
                company: document.getElementById('company').value || 'Not specified',
                subject: document.getElementById('subject').value,
                message: document.getElementById('message').value,
                appointment_requested: appointmentRequested ? 'Yes' : 'No',
                preferred_datetime: estDateTime
            };
            
            // Send email
            emailjs.send("service_gf8ewl9", "template_nad2dyc", params)
                .then(() => {
                    if (appointmentRequested) {
                        showAlert("Thanks for your message and appointment request! We'll get back to you within 24 hours with a meeting invite.", 'success');
                    } else {
                        showAlert("Thanks for your message! We'll get back to you within 24 hours.", 'success');
                    }
                    document.getElementById('contactForm').reset();
                    document.getElementById('appointmentFields').classList.remove('show');
                })
                .catch((error) => {
                    console.error('Error:', error);
                    showAlert("Sorry, there was an error sending your message. Please try again or email us directly at info@web3fuel.io", 'error');
                })
                .finally(() => {
                    // Re-enable button
                    submitBtn.disabled = false;
                    submitBtn.textContent = originalText;
                });
        }

        // Initialize page
        document.addEventListener('DOMContentLoaded', function() {
            // Set minimum date to today for datetime picker
            const datetimeInput = document.getElementById('datetime');
            if (datetimeInput) {
                const now = new Date();
                now.setMinutes(now.getMinutes() - now.getTimezoneOffset());
                datetimeInput.min = now.toISOString().slice(0, 16);
            }
        });
    </script>
</body>
</html>
'''

@contact_bp.route('/')
def contact():
    return render_template_string(contact_template)

# For standalone testing
if __name__ == '__main__':
    app = Flask(__name__)
    app.register_blueprint(contact_bp)
    app.run(debug=True)