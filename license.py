import streamlit as st

def show_license_page():
    st.markdown("""
    <style>
    .license-title {
        font-size: 24px;
        font-weight: bold;
        text-align: center;
        margin-bottom: 20px;
    }
    .license-text {
        font-size: 14px;
        line-height: 1.5;
        margin-bottom: 10px;
    }
    .license-disclaimer {
        font-size: 14px;
        line-height: 1.5;
        margin-top: 20px;
        font-style: italic;
    }
    </style>
    """, unsafe_allow_html=True)

    st.markdown('<div class="license-title">The 3-Clause BSD License Content</div>', unsafe_allow_html=True)
    
    st.markdown('<div class="license-text">Copyright © 2024 Helmholtz Munich</div>', unsafe_allow_html=True)
    
    st.markdown('<div class="license-text">Redistribution and use in source and binary forms, with or without modification, are permitted provided that the following conditions are met:</div>', unsafe_allow_html=True)
    
    st.markdown("""
    <div class="license-text">
    1. Redistributions of source code must retain the above copyright notice, this list of conditions and the following disclaimer.<br>
    2. Redistributions in binary form must reproduce the above copyright notice, this list of conditions and the following disclaimer in the documentation and/or other materials provided with the distribution.<br>
    3. Neither the name of the copyright holder nor the names of its contributors may be used to endorse or promote products derived from this software without specific prior written permission.
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("""
    <div class="license-disclaimer">
    THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
    </div>
    """, unsafe_allow_html=True)
